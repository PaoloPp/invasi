def round_floats(obj):
    if isinstance(obj, dict):
        return {key: round_floats(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [round_floats(element) for element in obj]
    elif isinstance(obj, float):
        return round(obj, 2)
    else:
        return obj