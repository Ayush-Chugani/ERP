from dataclasses import dataclass
from . import models as m

@dataclass(frozen=True)
class Resource:
    model: type
    path: str
    parent: str | None
    institution: str | None
    campus: str | None = None
    department: str | None = None

RESOURCES=(
 Resource(m.University,'universities',None,None),
 Resource(m.Institution,'institutions','university','pk'),
 Resource(m.Campus,'campuses','institution','institution','pk'),
 Resource(m.Department,'departments','campus','campus__institution','campus','pk'),
 Resource(m.Programme,'programmes','department','department__campus__institution','department__campus','department'),
 Resource(m.ProgrammeSpecialization,'programme-specializations','programme','programme__department__campus__institution','programme__department__campus','programme__department'),
 Resource(m.Building,'buildings','campus','campus__institution','campus'),
 Resource(m.Room,'rooms','building','building__campus__institution','building__campus'),
)
BY_MODEL={r.model:r for r in RESOURCES}
BY_PATH={r.path:r for r in RESOURCES}

def writable(model):
    return tuple(f for f in model._meta.fields if not f.primary_key and f.name not in ('created_at','updated_at'))
