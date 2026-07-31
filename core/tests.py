from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from core.seo import resolve_og_image_url, seo_context


class SeoImageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", HTTP_HOST="www.example.com")

    def test_homepage_uses_absolute_brand_logo(self):
        context = seo_context(
            request=self.request,
            title="Story of Flowers",
            description="Premium flowers and gifts.",
        )

        self.assertEqual(
            context["seo_og_image"],
            "http://www.example.com/static/img/logo.png",
        )
        self.assertEqual(context["seo_og_type"], "website")

    def test_product_uses_primary_gallery_image(self):
        product = SimpleNamespace(
            og_image=None,
            images=[
                SimpleNamespace(
                    image=SimpleNamespace(url="/media/products/secondary.jpg"),
                    is_primary=False,
                ),
                SimpleNamespace(
                    image=SimpleNamespace(url="/media/products/primary.jpg"),
                    is_primary=True,
                ),
            ],
        )

        self.assertEqual(
            resolve_og_image_url(obj=product, request=self.request),
            "http://www.example.com/media/products/primary.jpg",
        )

    def test_custom_social_image_takes_precedence(self):
        product = SimpleNamespace(
            og_image=SimpleNamespace(url="/media/seo/products/custom.jpg"),
            images=[
                SimpleNamespace(
                    image=SimpleNamespace(url="/media/products/primary.jpg"),
                    is_primary=True,
                )
            ],
        )

        self.assertEqual(
            resolve_og_image_url(obj=product, request=self.request),
            "http://www.example.com/media/seo/products/custom.jpg",
        )
