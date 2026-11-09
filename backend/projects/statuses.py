from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Project, ProjectStatusSetting


def project_status_options():
    settings = {item.status: item for item in ProjectStatusSetting.objects.all()}
    return [
        {"value": value, "label": settings[value].label if value in settings else label,
         "enabled": value not in settings or settings[value].enabled}
        for value, label in Project.Status.choices
    ]


@api_view(["GET"])
def project_statuses(request):
    return Response(project_status_options())
