from itertools import cycle

def set_year(_month):
    months = []
    tmp_months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    pool = cycle(tmp_months)
    for item in pool:
        if (item == _month) and (not months):
            months.append(item)
        elif (months) and (item != _month):
            months.append(item)
        elif (months) and (item == _month):
            break
    return months