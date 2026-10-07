from django.test import SimpleTestCase,override_settings
from apps.employee_hr.crypto import IdentifierCipher,IdentifierCryptoError,configured_cipher

class CryptoBoundaryTests(SimpleTestCase):
    def setUp(self):
        # Synthetic test-only key material, never deployment settings.
        self.cipher=IdentifierCipher(keys={1:b'a'*32},active_version=1,fingerprint_key=b'h'*32)

    def test_randomized_encryption_and_global_canonical_fingerprints(self):
        first=self.cipher.protect(kind='pan',employee_id=10,value=' abcde1234f ')
        second=self.cipher.protect(kind='pan',employee_id=20,value='ABCDE1234F')
        self.assertNotEqual(first.ciphertext,second.ciphertext)
        self.assertEqual(first.fingerprint,second.fingerprint)
        self.assertEqual(first.masked,'******234F')
        self.assertNotIn(b'ABCDE1234F',first.ciphertext)
        self.assertEqual(self.cipher._decrypt(kind='pan',employee_id=10,ciphertext=first.ciphertext),'ABCDE1234F')
        self.assertNotIn('ABCDE1234F',repr(first))

    def test_authentication_binds_owner_kind_and_ciphertext(self):
        value=self.cipher.protect(kind='bank',employee_id=10,value='123456789012')
        for kind,owner,blob in [('bank',11,value.ciphertext),('aadhaar',10,value.ciphertext),('bank',10,value.ciphertext[:-1]+bytes([value.ciphertext[-1]^1]))]:
            with self.assertRaises(IdentifierCryptoError):self.cipher._decrypt(kind=kind,employee_id=owner,ciphertext=blob)

    def test_rotation_keeps_fingerprint_and_old_key_readiness(self):
        value=self.cipher.protect(kind='bank',employee_id=10,value='123456789012')
        rotated=IdentifierCipher(keys={1:b'a'*32,2:b'b'*32},active_version=2,fingerprint_key=b'h'*32)
        replacement=rotated.reencrypt(kind='bank',employee_id=10,ciphertext=value.ciphertext)
        self.assertEqual(value.fingerprint,replacement.fingerprint)
        self.assertEqual(replacement.ciphertext[4:6],b'\x00\x02')
        self.assertEqual(rotated._decrypt(kind='bank',employee_id=10,ciphertext=replacement.ciphertext),'123456789012')

    @override_settings(EMPLOYEE_HR_ENCRYPTION_KEYS={},EMPLOYEE_HR_ACTIVE_KEY_VERSION=0,EMPLOYEE_HR_FINGERPRINT_KEY='')
    def test_missing_keys_and_invalid_identifiers_fail_without_echo(self):
        with self.assertRaises(IdentifierCryptoError):configured_cipher()
        with self.assertRaises(IdentifierCryptoError) as captured:self.cipher.protect(kind='pan',employee_id=10,value='DO-NOT-ECHO-THIS')
        self.assertNotIn('DO-NOT-ECHO-THIS',str(captured.exception))
        with self.assertRaises(IdentifierCryptoError):IdentifierCipher(keys={1:b'a'*32},active_version=1,fingerprint_key=b'a'*32)
