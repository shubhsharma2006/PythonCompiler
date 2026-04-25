from __future__ import annotations


def bind_call_arguments(
    function_name: str,
    params: list[str],
    defaults: list[object],
    args: list[object],
    kwargs: dict[str, object] | None = None,
    *,
    kwonly_params: list[str] | None = None,
    kwonly_defaults: dict[str, object] | None = None,
    vararg_name: str | None = None,
    kwarg_name: str | None = None,
) -> dict[str, object]:
    kwargs = dict(kwargs or {})
    kwonly_params = list(kwonly_params or [])
    kwonly_defaults = dict(kwonly_defaults or {})

    if vararg_name is None and len(args) > len(params):
        raise ValueError(f"function {function_name!r} expects at most {len(params)} arguments, got {len(args)}")

    values: dict[str, object] = {}
    for index, arg in enumerate(args[: len(params)]):
        values[params[index]] = arg

    if vararg_name is not None:
        values[vararg_name] = tuple(args[len(params):])

    extra_kwargs: dict[str, object] = {}
    allowed_names = set(params) | set(kwonly_params)
    for name, value in kwargs.items():
        if name in allowed_names:
            if name in values:
                raise ValueError(f"function {function_name!r} got multiple values for argument {name!r}")
            values[name] = value
            continue
        if kwarg_name is None:
            raise ValueError(f"function {function_name!r} got unexpected keyword argument {name!r}")
        extra_kwargs[name] = value

    first_default_index = len(params) - len(defaults)
    for index, name in enumerate(params):
        if name in values:
            continue
        default_index = index - first_default_index
        if 0 <= default_index < len(defaults):
            values[name] = defaults[default_index]
            continue
        raise ValueError(f"function {function_name!r} missing required argument {name!r}")

    for name in kwonly_params:
        if name in values:
            continue
        if name in kwonly_defaults:
            values[name] = kwonly_defaults[name]
            continue
        raise ValueError(f"function {function_name!r} missing required keyword-only argument {name!r}")

    if kwarg_name is not None:
        values[kwarg_name] = extra_kwargs

    return values
