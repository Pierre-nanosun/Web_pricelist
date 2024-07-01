
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('select_products/', views.select_products, name='select_products'),
    path('input_coefficients/<int:config_id>/', views.input_coefficients, name='input_coefficients'),
    path('generate_files/<int:config_id>/', views.generate_files, name='generate_files'),
    path('results/', views.results, name='results'),
    path('download_pdf/', views.download_pdf, name='download_pdf'),
    path('download_excel/', views.download_excel, name='download_excel'),
    path('view_pdf/', views.view_pdf, name='view_pdf'),
    path('oauth/', include('social_django.urls', namespace='social')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)