from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('prestadores/', include('cadastro.urls')),
    path('', RedirectView.as_view(url='/prestadores/', permanent=False)),
]
