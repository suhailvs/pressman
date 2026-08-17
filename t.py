from myapp.models import Pickup, PickupItem
from django.db.models import Count
for p in Pickup.objects.all():
    i = PickupItem.objects.filter(pickup=p).values('item').annotate(c=Count('item'))
    for j in i:
        if j['c']>1: 
            print(i, p.id, p.location.name, p.created_at)

