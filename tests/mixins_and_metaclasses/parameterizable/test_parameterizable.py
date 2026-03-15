import json
from typing import Any


from mixinforge.mixins_and_metaclasses.parameterizable_mixin import ParameterizableMixin
from mixinforge.utility_functions.json_processor import loadjs


class MyParam(ParameterizableMixin):
    def __init__(
        self,
        a: int,
        b: int = 2,
        c: str = "x",
        d: Any = None,
        *,
        e: int = 5,
        f: int = 7,
        **kwargs,
    ) -> None:
        # store everything so that get_params can see it
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.e = e
        self.f = f
        # an auxiliary-only parameter (not present among defaults)
        self.verbose = kwargs.get("verbose", False)

    def get_params(self) -> dict[str, Any]:
        return {
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "d": self.d,
            "e": self.e,
            "f": self.f,
            "verbose": self.verbose,
        }


class ParentParam(ParameterizableMixin):
    def __init__(self, x: int = 1, y: int = 2) -> None:
        self.x = x
        self.y = y

    def get_params(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y}


class ChildParam(ParentParam):
    def __init__(self, x: int = 1, y: int = 2, z: int = 3) -> None:
        super().__init__(x=x, y=y)
        self.z = z

    def get_params(self) -> dict[str, Any]:
        params = super().get_params()
        params["z"] = self.z
        return params


def test_base_class_defaults_and_jsparams_are_empty():
    # Base class returns empty params dict
    base = ParameterizableMixin()
    assert base.get_params() == {}

    js = base.get_jsparams()
    assert isinstance(js, str)
    assert loadjs(js) == {}


def test_get_default_params_collects_init_defaults_and_sorts_keys():
    # Required-only param 'a' must NOT be in defaults
    expected_defaults = {"b": 2, "c": "x", "d": None, "e": 5, "f": 7}

    got = MyParam.get_default_params()
    # Ensure keys are sorted lexicographically
    assert list(got.keys()) == sorted(expected_defaults.keys())
    assert got == expected_defaults

    # JSON variant round-trips to the same mapping
    js = MyParam.get_default_jsparams()
    assert loadjs(js) == expected_defaults


def test_instance_jsparams_is_dump_of_params_dict():
    obj = MyParam(a=10, b=20, c="ok", e=50, f=70)

    params = obj.get_params()
    js = obj.get_jsparams()

    # get_jsparams returns dumpjs of a plain dict → loadjs returns the same dict
    assert loadjs(js) == params

    # And dumpjs/loadjs are indeed JSON – the payload is a JSON string
    # Validate it parses with the stdlib json loader too
    json.loads(js)


def test_repr_includes_class_name_and_params():
    # Base class (no params)
    base = ParameterizableMixin()
    assert repr(base) == "ParameterizableMixin({})"

    # Subclass (with params)
    obj = MyParam(a=1)
    # The repr should look like "MyParam({'a': 1, 'b': 2, ...})"
    r = repr(obj)
    assert r.startswith("MyParam(")
    assert "'a': 1" in r
    assert "'b': 2" in r
    assert "'verbose': False" in r


def test_get_params_can_extend_parent_params_with_super():
    """Child get_params can reuse parent params and extend them."""
    child = ChildParam(x=10, y=20, z=30)
    base = ParentParam(x=1, y=2)

    params = child.get_params()

    assert params == {"x": 10, "y": 20, "z": 30}
    assert set(params.keys()) == {"x", "y", "z"}
    assert base.get_params() == {"x": 1, "y": 2}


def test_extend_parent_params_accepts_kwargs_and_overrides():
    """Helper merges parent params with provided keyword overrides."""
    child = ChildParam(x=10, y=20, z=30)

    params = child._extend_parent_params(z=child.z, y=99)

    assert params["x"] == 10
    assert params["y"] == 99
    assert params["z"] == 30
    assert set(params.keys()) == {"x", "y", "z"}


def test_extend_parent_params_base_class_falls_back_to_new_params():
    base = ParameterizableMixin()
    params = base._extend_parent_params(b=2, a=1)
    assert params == {"a": 1, "b": 2}


def test_extend_parent_params_child_without_get_params():
    class NoParamsChild(ParameterizableMixin):
        pass

    child = NoParamsChild()
    params = child._extend_parent_params(c=3, a=1, b=2)
    assert params == {"a": 1, "b": 2, "c": 3}


def test_extend_parent_params_grandchild_get_params_use_case():
    class ClassA(ParameterizableMixin):
        def __init__(self, a: int = 1) -> None:
            self.a = a

        def get_params(self) -> dict[str, Any]:
            return {"a": self.a}

    class ClassB(ClassA):
        def __init__(self, a: int = 1, b: int = 2) -> None:
            super().__init__(a=a)
            self.b = b

        def get_params(self) -> dict[str, Any]:
            return self._extend_parent_params(b=self.b)

    obj = ClassB(a=10, b=20)
    params = obj.get_params()
    assert params == {"a": 10, "b": 20}


def test_clone_creates_new_instance_and_deepcopies_params():
    class ListParam(ParameterizableMixin):
        def __init__(self, items: list[int], other: int = 0) -> None:
            self.items = items
            self.other = other

        def get_params(self) -> dict[str, Any]:
            return {"items": self.items, "other": self.other}

    original = ListParam(items=[1, 2, 3], other=10)
    cloned = original.clone()

    assert cloned is not original
    assert cloned.items == [1, 2, 3]
    assert cloned.items is not original.items  # deepcopy prevents shared mutable state

    # Test override
    cloned_override = original.clone(other=20)
    assert cloned_override.items == [1, 2, 3]
    assert cloned_override.items is not original.items
    assert cloned_override.other == 20


def test_clone_with_nested_mutable_kwargs():
    class DictParam(ParameterizableMixin):
        def __init__(self, config: dict[str, Any]) -> None:
            self.config = config

        def get_params(self) -> dict[str, Any]:
            return {"config": self.config}

    original = DictParam(config={"a": 1})

    # Clone with a mutable kwarg
    new_config = {"a": 2, "b": [1, 2, 3]}
    cloned = original.clone(config=new_config)

    assert cloned.config == {"a": 2, "b": [1, 2, 3]}
    assert cloned.config is not new_config  # Should be a deepcopy
    assert cloned.config["b"] is not new_config["b"]


def test_clone_with_invalid_params_raises_error():
    import pytest

    class SimpleParam(ParameterizableMixin):
        def __init__(self, a: int) -> None:
            self.a = a

        def get_params(self) -> dict[str, Any]:
            return {"a": self.a}

    original = SimpleParam(a=1)

    with pytest.raises(TypeError):
        original.clone(invalid_param=42)
