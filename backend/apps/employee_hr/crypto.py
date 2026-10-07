"""Internal cryptographic primitive, not an authorization or decrypt API.

HR use cases must authorize and dual-audit before decrypting persisted records.
Fingerprint keys stay stable across encryption-key rotation.
"""
import base64
import hashlib
import hmac
import os
import re
from dataclasses import dataclass,field
from django.conf import settings
from django.views.decorators.debug import sensitive_variables
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'SHR1'
KINDS=frozenset(('bank','pan','aadhaar'))

class IdentifierCryptoError(ValueError):
    def __init__(self):super().__init__('Identifier operation failed.')

@dataclass(frozen=True,repr=False)
class ProtectedIdentifier:
    ciphertext:bytes=field(repr=False)
    fingerprint:str=field(repr=False)
    masked:str
    last4:str

@sensitive_variables('value','canonical')
def canonical_identifier(kind,value):
    if kind not in KINDS or not isinstance(value,str):raise IdentifierCryptoError()
    canonical=value.strip().upper() if kind=='pan' else value.replace(' ','').replace('-','')
    pattern={'bank':r'[0-9]{6,34}','pan':r'[A-Z]{5}[0-9]{4}[A-Z]','aadhaar':r'[2-9][0-9]{11}'}[kind]
    if re.fullmatch(pattern,canonical) is None:raise IdentifierCryptoError()
    # This is format normalization, not issuer/identity verification.
    return canonical

@sensitive_variables('value')
def masked_identifier(value):
    if not isinstance(value,str) or len(value)<4:raise IdentifierCryptoError()
    return '*'*(len(value)-4)+value[-4:]

class IdentifierCipher:
    @sensitive_variables('keys','fingerprint_key')
    def __init__(self,*,keys,active_version,fingerprint_key):
        if (not isinstance(keys,dict) or not keys or type(active_version) is not int
            or active_version not in keys or not isinstance(fingerprint_key,bytes) or len(fingerprint_key)!=32):
            raise IdentifierCryptoError()
        if any(type(v) is not int or not 1<=v<=65535 or not isinstance(k,bytes) or len(k)!=32 for v,k in keys.items()):
            raise IdentifierCryptoError()
        if any(hmac.compare_digest(fingerprint_key,key) for key in keys.values()):raise IdentifierCryptoError()
        self._keys=dict(keys);self._active=active_version;self._fingerprint_key=fingerprint_key

    def _context(self,kind,employee_id,header):
        if kind not in KINDS or type(employee_id) is not int or employee_id<=0:raise IdentifierCryptoError()
        return b'SIMS:M16:'+kind.encode('ascii')+b':'+str(employee_id).encode('ascii')+b':'+header

    @sensitive_variables('value','canonical')
    def protect(self,*,kind,employee_id,value):
        canonical=canonical_identifier(kind,value)
        header=MAGIC+self._active.to_bytes(2,'big');nonce=os.urandom(12)
        context=self._context(kind,employee_id,header)
        ciphertext=header+nonce+AESGCM(self._keys[self._active]).encrypt(nonce,canonical.encode('ascii'),context)
        if len(ciphertext)>1024:raise IdentifierCryptoError()
        fingerprint=hmac.new(self._fingerprint_key,b'SIMS:M16:'+kind.encode('ascii')+b':'+canonical.encode('ascii'),hashlib.sha256).hexdigest()
        return ProtectedIdentifier(ciphertext,fingerprint,masked_identifier(canonical),canonical[-4:])

    @sensitive_variables('plaintext')
    def _decrypt(self,*,kind,employee_id,ciphertext):
        if not isinstance(ciphertext,bytes) or not 34<=len(ciphertext)<=1024 or ciphertext[:4]!=MAGIC:raise IdentifierCryptoError()
        version=int.from_bytes(ciphertext[4:6],'big');key=self._keys.get(version)
        if key is None:raise IdentifierCryptoError()
        try:
            plaintext=AESGCM(key).decrypt(ciphertext[6:18],ciphertext[18:],self._context(kind,employee_id,ciphertext[:6])).decode('ascii')
            return canonical_identifier(kind,plaintext)
        except (InvalidTag,UnicodeError,ValueError):raise IdentifierCryptoError() from None

    @sensitive_variables('plaintext')
    def reencrypt(self,*,kind,employee_id,ciphertext):
        plaintext=self._decrypt(kind=kind,employee_id=employee_id,ciphertext=ciphertext)
        return self.protect(kind=kind,employee_id=employee_id,value=plaintext)

@sensitive_variables('ring','keys','fingerprint')
def configured_cipher():
    try:
        ring=settings.EMPLOYEE_HR_ENCRYPTION_KEYS
        keys={int(version):base64.b64decode(value,validate=True) for version,value in ring.items()}
        fingerprint=base64.b64decode(settings.EMPLOYEE_HR_FINGERPRINT_KEY,validate=True)
        return IdentifierCipher(keys=keys,active_version=settings.EMPLOYEE_HR_ACTIVE_KEY_VERSION,fingerprint_key=fingerprint)
    except (ValueError,TypeError,AttributeError):raise IdentifierCryptoError() from None
