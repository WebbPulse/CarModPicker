"""SAFE-09: pin the MetaData.naming_convention keys applied to Base.

If this test fails, someone silently dropped the naming convention or altered
its key set. The expected keys (`ix`, `uq`, `ck`, `fk`, `pk`) are the
SQLAlchemy-recommended convention locked by D-11.
"""

from __future__ import annotations


def test_metadata_naming_convention_has_five_expected_keys() -> None:
    """SAFE-09 contract: Base.metadata.naming_convention has exactly 5 keys."""
    from app.db.base_class import Base

    convention = Base.metadata.naming_convention
    assert isinstance(convention, dict)
    assert set(convention.keys()) == {
        "ix",
        "uq",
        "ck",
        "fk",
        "pk",
    }, f"Unexpected naming_convention keys: {sorted(convention.keys())}"


def test_metadata_naming_convention_fk_template_is_sqlalchemy_recommended() -> None:
    """SAFE-09 contract: fk template matches the SQLAlchemy-recommended shape (D-11)."""
    from app.db.base_class import Base

    convention = Base.metadata.naming_convention
    assert (
        convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    ), f"fk template drift: {convention['fk']!r}"
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["ix"] == "ix_%(column_0_label)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
