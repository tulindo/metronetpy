import yaml


def parse_mandatory_key(obj, key):
    return obj[key]


def parse_key(obj, key, default):
    if obj is None or key not in obj:
        return default
    return obj[key]


class Configuration(object):
    def __init__(self, path):
        with open(path, "r") as yamlfile:
            try:
                config = yaml.load(yamlfile, Loader=yaml.BaseLoader)
            except yaml.YAMLError as exc:
                print(exc)
                exit()

        # TODO: Add Validation

        section = config["metronet"]
        self.username = section["username"]
        self.password = section["password"]

        section = config["server"]
        self.listen = parse_key(section, "listen", "0.0.0.0")
        self.port = parse_key(section, "port", 5027)

        self.sensors = []
        section = config["inputs"]
        for input in section:
            self.sensors.append(
                {
                    "id": int(parse_mandatory_key(input, "id")),
                    "type": parse_mandatory_key(input, "type"),
                    "name": parse_key(input, "name", None),
                }
            )
