"""One package per deployable domain.

A change under `app/domains/<name>/` belongs to that name's function alone; a
change under `app/common/` fans out to whichever domains import it.
"""
