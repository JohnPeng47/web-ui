from scripts.portswigger.data.server_side import SQL_INJECTION_LABS
import json

with open("scripts/portswigger/port_swigger_labs.json", "r") as r:
    labs = json.loads(r.read())
    labs["sql_injection"] = SQL_INJECTION_LABS

with open("scripts/portswigger/port_swigger_labs.json", "w") as f:
    f.write(json.dumps(labs, indent=4))