import engine
import request

raw_data = request.files()
planner_data = engine.planner(raw_data)
"""
planner_data = {data, summary, skills}

data={
    "event": "sample event",
    "priority": 1,
    "details": "sample details",
    "deadline": "2024-06-30",
}

skills={
}
"""


datas = sorted(planner_data['data'], key=lambda x: x.get("priority"), reverse=True)

result = []
for data in datas:

    result.append({
        "event": data.get("event"),
        "priority": data.get("priority"),
        "details": data.get("details"),
        "deadline": data.get("deadline"),
        "start_date": start_data,
        "end_date": end_data
    })