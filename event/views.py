from rest_framework import generics, throttling
from rest_framework.response import Response
from .models import Event
from .serializers import EventCreateSerializer


def get_client_country(request):
    cf_country = request.META.get("HTTP_CF_IPCOUNTRY")
    if cf_country:
        return cf_country
    return None


class EventThrottle(throttling.AnonRateThrottle):
    rate = "60/min"


class EventCreateView(generics.CreateAPIView):
    queryset = Event.objects.all()
    serializer_class = EventCreateSerializer
    throttle_classes = [EventThrottle]

    def perform_create(self, serializer):
        serializer.save(country=get_client_country(self.request))

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response(status=201)
