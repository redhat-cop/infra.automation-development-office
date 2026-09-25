"""Validate Helm-rendered image references without contacting a registry."""
import json
import sys

import yaml


def images(value):
    """Include images in init containers, hooks, Jobs and nested pod specs."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "image" and isinstance(child, str):
                yield child
            else:
                yield from images(child)
    elif isinstance(value, list):
        for child in value:
            yield from images(child)


def validate(documents, registries):
    """Return errors without printing manifests, which may contain secrets."""
    errors = []
    found = set()
    for document in documents:
        found.update(images(document))
    if not found:
        errors.append("Chart rendered no image references; verify the supplied chart and values.")
    for ref in sorted(found):
        host, separator, name = ref.partition("/")
        if not separator or host not in registries:
            errors.append("An image does not use an explicitly allowed disconnected registry.")
        if not name or (":" not in name and "@sha256:" not in name) or name.endswith(":latest"):
            errors.append("An image is missing a pinned tag/digest or uses latest.")
    return errors


def main():
    """Validate the local render supplied by the role."""
    with open(sys.argv[1], encoding="utf-8") as stream:
        errors = validate(yaml.safe_load_all(stream), json.loads(sys.argv[2]))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Rendered image references use the allowed disconnected registries.")


if __name__ == "__main__":
    main()
