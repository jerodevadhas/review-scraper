from django.shortcuts import redirect
from django.views.generic import FormView, ListView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .forms import URLForm
from .models import Review
from .scraper import ReviewScraper
from datetime import datetime

# ---- HomeView (form page) ----
class HomeView(FormView):
    template_name = 'scraper/home.html'
    form_class = URLForm
    success_url = reverse_lazy('scraper:results')

    def form_valid(self, form):
        url = form.cleaned_data['url']
        max_reviews = form.cleaned_data.get('max_reviews', 20)

        recent = Review.objects.filter(url=url, scraped_at__gte=timezone.now() - timezone.timedelta(hours=1))
        if recent.exists():
            self.request.session['review_url'] = url
            messages.info(self.request, f"Using cached reviews for {url}")
            return redirect('scraper:results')

        try:
            reviews_data = ReviewScraper.scrape(url, max_reviews)
        except Exception as e:
            messages.error(self.request, f"Error scraping: {str(e)}")
            return self.form_invalid(form)

        if not reviews_data:
            messages.warning(self.request, "No reviews found on this page.")
            return self.form_invalid(form)

        saved_count = 0
        for data in reviews_data:
            # Convert date string to datetime if needed
            date_val = data.get('date')
            if isinstance(date_val, str):
                try:
                    date_val = datetime.strptime(date_val, '%Y-%m-%d')
                except:
                    date_val = None
            obj, created = Review.objects.get_or_create(
                url=url,
                reviewer=data['reviewer'],
                date=date_val,
                defaults={
                    'rating': data['rating'],
                    'content': data['content'],
                }
            )
            if created:
                saved_count += 1

        self.request.session['review_url'] = url
        messages.success(self.request, f"Successfully scraped and saved {saved_count} reviews.")
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

# ---- ResultsView (display scraped reviews) ----
class ResultsView(ListView):
    template_name = 'scraper/results.html'
    context_object_name = 'reviews'
    paginate_by = 10

    def get_queryset(self):
        url = self.request.session.get('review_url')
        if not url:
            return Review.objects.none()
        return Review.objects.filter(url=url).order_by('-scraped_at', '-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['url'] = self.request.session.get('review_url')
        context['total'] = Review.objects.filter(url=context['url']).count()
        return context

# ---- ScrapeAjaxView – Updated with all fields ----
class ScrapeAjaxView(View):
    def post(self, request):
        form = URLForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': 'Invalid URL'}, status=400)

        url = form.cleaned_data['url']
        max_reviews = form.cleaned_data.get('max_reviews', 20)

        try:
            reviews_data = ReviewScraper.scrape(url, max_reviews)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

        if not reviews_data:
            return JsonResponse({'error': 'No reviews found'}, status=404)

        saved = 0
        for data in reviews_data:
            date_val = data.get('date')
            if isinstance(date_val, str):
                try:
                    date_val = datetime.strptime(date_val, '%Y-%m-%d')
                except:
                    date_val = None
            obj, created = Review.objects.get_or_create(
                url=url,
                reviewer=data['reviewer'],
                date=date_val,
                defaults={
                    'rating': data['rating'],
                    'content': data['content'],
                }
            )
            if created:
                saved += 1

        # Build the response with ALL fields
        reviews_list = []
        for r in reviews_data:
            date_val = r.get('date')
            if hasattr(date_val, 'strftime'):
                date_str = date_val.strftime('%Y-%m-%d %H:%M')
            else:
                date_str = str(date_val) if date_val else ''

            reviews_list.append({
                'reviewer': r.get('reviewer', 'Anonymous'),
                'rating': r.get('rating', 0),
                'content': r.get('content', ''),
                'date': date_str,
                'avatar': r.get('avatar', ''),
                'is_verified': r.get('is_verified', False),
                'images': r.get('images', []),
            })

        return JsonResponse({
            'success': True,
            'count': saved,
            'reviews': reviews_list,   # all scraped reviews
        })