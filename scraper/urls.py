from django.urls import path
from .views import HomeView, ResultsView, ScrapeAjaxView

app_name = 'scraper'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('results/', ResultsView.as_view(), name='results'),
    path('ajax-scrape/', ScrapeAjaxView.as_view(), name='ajax_scrape'),
]