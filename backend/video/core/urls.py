from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core.views import TaskExecutionViewSet


router = DefaultRouter()
router.register(r'tasks', TaskExecutionViewSet, basename='admin-task')

urlpatterns = [
    path('', include(router.urls)),
]
