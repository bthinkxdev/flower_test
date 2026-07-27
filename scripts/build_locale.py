"""
Build storefront gettext catalogs (en/ar) and compile .mo files.

Usage:
  python scripts/build_locale.py

- Collects msgids from templates/, accounts/templates/, core/templates/, and Python _()
- Applies curated Arabic overrides (AR)
- Auto-fills remaining strings via deep-translator (cached in scripts/.locale_ar_cache.json)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOTS = [
    ROOT / "templates",
    ROOT / "accounts" / "templates",
    ROOT / "core" / "templates",
]
CACHE_PATH = ROOT / "scripts" / ".locale_ar_cache.json"

# Curated Arabic translations (source of truth for high-visibility UI).
AR: dict[str, str] = {
    # Brand / SEO
    "Story of Flowers": "قصة الزهور",
    "Luxury Flowers & Gifts | Story of Flowers": "زهور وهدايا فاخرة | قصة الزهور",
    "Luxury Flowers & Gifts": "زهور وهدايا فاخرة",
    "Shop | Story of Flowers": "تسوق | قصة الزهور",
    "Shop All Flowers & Gifts": "تسوق جميع الزهور والهدايا",
    "%(title)s | Story of Flowers": "%(title)s | قصة الزهور",
    "%(name)s | Story of Flowers": "%(name)s | قصة الزهور",
    "%(name)s — premium flowers and gifts delivered in Qatar.": "%(name)s — زهور وهدايا فاخرة تُوصل في قطر.",
    "Browse %(name)s flowers and gifts with same-day delivery in Qatar.": "تصفح زهور وهدايا %(name)s مع التوصيل في نفس اليوم في قطر.",
    "Browse premium flowers and gifts with same-day delivery across Qatar.": "تصفح الزهور والهدايا الفاخرة مع التوصيل في نفس اليوم في جميع أنحاء قطر.",
    "Low stock — only %(count)s left": "مخزون منخفض — تبقى %(count)s فقط",
    "Low stock — only {{ count }} left": "مخزون منخفض — تبقى {{ count }} فقط",
    "Send premium flowers and gifts with same-day delivery across Qatar.": "أرسل زهوراً وهدايا فاخرة مع توصيل في نفس اليوم في جميع أنحاء قطر.",
    "Floward Qatar": "فلاورد قطر",
    "Qatar": "قطر",
    # Header / shell
    "Express Delivery": "توصيل سريع",
    "No Address Hassle": "بدون متاعب العنوان",
    "Premium Flowers & Gifts": "زهور وهدايا فاخرة",
    "Delivery to": "التوصيل إلى",
    "Delivery country": "بلد التوصيل",
    "Language": "اللغة",
    "Currency": "العملة",
    "Menu": "القائمة",
    "Search": "بحث",
    "Search flowers, gifts...": "ابحث عن زهور، هدايا...",
    "Searching...": "جاري البحث...",
    "Search results": "نتائج البحث",
    "Wishlist": "المفضلة",
    "Cart": "السلة",
    "Account": "الحساب",
    "My Account": "حسابي",
    "Login": "تسجيل الدخول",
    "Log in": "تسجيل الدخول",
    "Logout": "تسجيل الخروج",
    "Cancel": "إلغاء",
    "Clear": "مسح",
    "Close": "إغلاق",
    "Your Cart": "سلتك",
    "Your cart items will appear here.": "ستظهر عناصر سلتك هنا.",
    "Mobile navigation": "التنقل للجوال",
    "Home": "الرئيسية",
    "Shop": "التسوق",
    "Shop All": "تسوق الكل",
    "Shop Now": "تسوق الآن",
    # Footer
    "Online flowers & gifts delivery in Qatar. Same-day delivery available.": "توصيل الزهور والهدايا عبر الإنترنت في قطر. يتوفر التوصيل في نفس اليوم.",
    "All Flowers": "جميع الزهور",
    "Best Sellers": "الأكثر مبيعاً",
    "Same Day": "توصيل اليوم",
    "Same Day Delivery": "توصيل في نفس اليوم",
    "Company": "الشركة",
    "Corporate Gifts": "هدايا الشركات",
    "Corporate Portal": "بوابة الشركات",
    "Get to Know Us": "تعرّف علينا",
    "About Us": "من نحن",
    "Blog": "المدونة",
    "Privacy Policy": "سياسة الخصوصية",
    "Customer Service": "خدمة العملاء",
    "Contact Us": "اتصل بنا",
    "FAQ": "الأسئلة الشائعة",
    "Contact": "تواصل",
    "Doha, Qatar": "الدوحة، قطر",
    "Customer support available 24/7": "دعم العملاء متاح على مدار الساعة",
    "All rights reserved.": "جميع الحقوق محفوظة.",
    # Homepage
    "Homepage content is being prepared.": "يتم تجهيز محتوى الصفحة الرئيسية.",
    "Promotions": "العروض",
    "View All": "عرض الكل",
    "Choose Gifts Now": "اختر الهدايا الآن",
    "Shop by Occasion": "تسوق حسب المناسبة",
    "Shop by Category": "تسوق حسب الفئة",
    "Shop by Recipient": "تسوق حسب المستلم",
    "Featured Brands": "علامات مميزة",
    "Featured brands": "علامات مميزة",
    "Brands You'll Love": "علامات ستعجبك",
    "Explore Unique Gift Ideas": "اكتشف أفكار هدايا فريدة",
    "Gifts for Every Moment": "هدايا لكل لحظة",
    "Scroll brands left": "تمرير العلامات لليسار",
    "Scroll brands right": "تمرير العلامات لليمين",
    "Customer Reviews": "آراء العملاء",
    "Follow Us": "تابعنا",
    "Follow us on Instagram": "تابعنا على إنستغرام",
    "Join Our Newsletter": "انضم إلى نشرتنا",
    "Get exclusive offers and gifting inspiration.": "احصل على عروض حصرية وإلهام للهدايا.",
    "Subscribe": "اشترك",
    "Email": "البريد الإلكتروني",
    "Email address": "البريد الإلكتروني",
    "Rating": "التقييم",
    "No products available.": "لا توجد منتجات متاحة.",
    "Express": "سريع",
    "New": "جديد",
    "Premium Collection": "مجموعة فاخرة",
    "Seasonal Collection": "مجموعة موسمية",
    "Luxury Collection": "مجموعة فاخرة",
    "Trending": "الأكثر رواجاً",
    "For Loved Ones": "لأحبائك",
    # PLP
    "Filters": "التصفية",
    "Clear filters": "مسح عوامل التصفية",
    "Clear Filters": "مسح عوامل التصفية",
    "No products match your filters.": "لا توجد منتجات تطابق عوامل التصفية.",
    "products": "منتجات",
    "Pagination": "ترقيم الصفحات",
    "Previous": "السابق",
    "Next": "التالي",
    "Category": "الفئة",
    "Occasion": "المناسبة",
    "Brand": "العلامة",
    "Price": "السعر",
    "Min": "الحد الأدنى",
    "Max": "الحد الأعلى",
    "All": "الكل",
    "Bestseller": "الأكثر مبيعاً",
    "In Stock": "متوفر",
    "Sort": "الترتيب",
    "Newest": "الأحدث",
    "Price: Low to High": "السعر: من الأقل إلى الأعلى",
    "Price: High to Low": "السعر: من الأعلى إلى الأقل",
    "Top Rated": "الأعلى تقييماً",
    "Apply": "تطبيق",
    "Try a different keyword or browse our collections.": "جرّب كلمة أخرى أو تصفح مجموعاتنا.",
    "Browse all categories": "تصفح جميع الفئات",
    # PDP
    "Select Option": "اختر الخيار",
    "Standard": "قياسي",
    "Add to Cart": "أضف إلى السلة",
    "View Cart": "عرض السلة",
    "Customize as Gift": "خصّص كهدية",
    "Out of stock": "غير متوفر",
    "In stock": "متوفر",
    "— order now": "— اطلب الآن",
    "order now": "اطلب الآن",
    "Reviews": "التقييمات",
    "Write a review": "اكتب تقييماً",
    "Submit Review": "إرسال التقييم",
    "Your review is pending moderation.": "تقييمك قيد المراجعة.",
    "Your review was not approved.": "لم تتم الموافقة على تقييمك.",
    "Only customers who purchased this product can write a review.": "يمكن فقط للعملاء الذين اشتروا هذا المنتج كتابة تقييم.",
    "to write a review after purchasing this product.": "لكتابة تقييم بعد شراء هذا المنتج.",
    "No reviews yet.": "لا توجد تقييمات بعد.",
    "Related Products": "منتجات ذات صلة",
    "View image": "عرض الصورة",
    "Delivery Estimate": "تقدير التوصيل",
    "Select a city": "اختر مدينة",
    "Delivery:": "التوصيل:",
    "to": "إلى",
    "Delivery: %(label)s to %(city)s": "التوصيل: %(label)s إلى %(city)s",
    "In stock(%(count)s) — order now": "متوفر(%(count)s) — اطلب الآن",
    # Cart
    "Your cart is empty.": "سلتك فارغة.",
    "Continue Shopping": "متابعة التسوق",
    "Continue shopping": "متابعة التسوق",
    "Proceed to Checkout": "المتابعة إلى الدفع",
    "Checkout": "إتمام الشراء",
    "Order Summary": "ملخص الطلب",
    "Subtotal": "المجموع الفرعي",
    "Quantity": "الكمية",
    "Remove": "إزالة",
    "Update": "تحديث",
    "Item": "عنصر",
    "Items": "عناصر",
    # Checkout
    "Confirm delivery details and payment to complete your order.": "أكد تفاصيل التوصيل والدفع لإتمام طلبك.",
    "Delivery Address": "عنوان التوصيل",
    "Payment Method": "طريقة الدفع",
    "Order Summary": "ملخص الطلب",
    "Gift voucher code": "رمز قسيمة الهدية",
    "Time slot": "الفترة الزمنية",
    "Select slot": "اختر فترة",
    "Date": "التاريخ",
    "Place Order & Pay": "تأكيد الطلب والدفع",
    "Place Order": "تأكيد الطلب",
    "Delivery Charge": "رسوم التوصيل",
    "Delivery Date": "تاريخ التوصيل",
    "Delivery Slot": "فترة التوصيل",
    "Delivery Instructions": "تعليمات التوصيل",
    "Shipping Address": "عنوان الشحن",
    "Billing": "الفوترة",
    "Payment": "الدفع",
    "Coupon": "قسيمة",
    "Coupon Discount": "خصم القسيمة",
    "Apply Coupon": "تطبيق القسيمة",
    "Gift Card": "بطاقة هدية",
    "Order Confirmed": "تم تأكيد الطلب",
    "Thank you for your order!": "شكراً لطلبك!",
    "Order Number": "رقم الطلب",
    "Track Order": "تتبع الطلب",
    "Address": "العنوان",
    "Addresses": "العناوين",
    "Add New Address": "إضافة عنوان جديد",
    "+ Add New Address": "+ إضافة عنوان جديد",
    "Edit Address": "تعديل العنوان",
    "Delete Address": "حذف العنوان",
    "Save Address": "حفظ العنوان",
    "Address Line 1": "سطر العنوان 1",
    "Address Line 2": "سطر العنوان 2",
    "Address line 1": "سطر العنوان 1",
    "Address line 2": "سطر العنوان 2",
    "City": "المدينة",
    "Contact Name": "اسم جهة الاتصال",
    "Phone": "الهاتف",
    "Phone number": "رقم الهاتف",
    "Postal Code": "الرمز البريدي",
    "Set as default": "تعيين كافتراضي",
    "Default": "افتراضي",
    "Guest checkout": "الدفع كضيف",
    "Checking out as guest — enter your details below.": "الدفع كضيف — أدخل بياناتك أدناه.",
    "Calculated at checkout": "يُحسب عند الدفع",
    "Are you sure you want to delete this address?": "هل أنت متأكد من حذف هذا العنوان؟",
    # Gift builder
    "Gift Builder": "منشئ الهدايا",
    "Customize Your Gift": "خصّص هديتك",
    "Choose a message, card, wrap, and delivery details — your preview updates as you go.": "اختر الرسالة والبطاقة والتغليف وتفاصيل التوصيل — تتحدّث المعاينة تلقائياً.",
    "Personal Message": "رسالة شخصية",
    "Written on your card — keep it short and personal.": "تُكتب على بطاقتك — اجعلها قصيرة وشخصية.",
    "Write your message…": "اكتب رسالتك…",
    "Greeting Card": "بطاقة تهنئة",
    "Pick a card design for your message.": "اختر تصميم بطاقة لرسالتك.",
    "Gift Wrap": "تغليف الهدية",
    "How your gift arrives.": "كيف تصل هديتك.",
    "Ribbon": "شريطة",
    "Photo Upload": "رفع صورة",
    "Add-ons": "إضافات",
    "Add-on": "إضافة",
    "Optional extras to complete the gift.": "إضافات اختيارية لإكمال الهدية.",
    "No add-ons available.": "لا توجد إضافات متاحة.",
    "No greeting cards for this occasion.": "لا توجد بطاقات تهنئة لهذه المناسبة.",
    "Delivery Preferences": "تفضيلات التسليم",
    "When and how we deliver.": "متى وكيف نُوصل.",
    "Delivery date": "تاريخ التسليم او الوصول",
    "Delivery slot": "فتحة التسليم",
    "Select a slot": "حدد فتحة",
    "Delivery instructions": "تعليمات التسليم",
    "Gate code, floor, landmark…": "رمز البوابة، الطابق، معلم…",
    "Gift Options": "خيارات الهدية",
    "Send anonymously": "أرسل بشكل مجهول",
    "Reveal sender after delivery": "إظهار المرسل بعد التسليم",
    "Gift receipt (hide prices on packing slip)": "إيصال هدية (إخفاء الأسعار من قسيمة التعبئة)",
    "Anonymous": "مجهول",
    "Gift Receipt": "إيصال هدية",
    "Added to cart!": "تمت الإضافة إلى السلة!",
    "Update Preview": "تحديث المعاينة",
    "Order Preview": "معاينة الطلب",
    "Live summary of your customization": "ملخص مباشر لتخصيصك",
    "Customization total": "إجمالي التخصيص",
    "Customize your gift to see a live preview here.": "خصّص هديتك لرؤية معاينة مباشرة هنا.",
    "Recipient phone": "هاتف المستلم",
    "Qty": "الكمية",
    "Add to cart": "أضف إلى السلة",
    "Midnight delivery": "توصيل منتصف الليل",
    "Your message will appear here...": "ستظهر رسالتك هنا...",
    "Preview": "معاينة",
    "Please fix the following:": "يرجى تصحيح ما يلي:",
    "Gift customization saved.": "تم حفظ تخصيص الهدية.",
    "Greeting card": "بطاقة تهنئة",
    "Gift wrap": "تغليف الهدية",
    "Photo upload": "رفع صورة",
    "Instructions": "التعليمات",
    "Prices hidden on packing slip": "الأسعار مخفية من قسيمة التعبئة",
    "Yes": "نعم",
    # Account / wishlist / subscriptions
    "My Wishlist": "قائمة أمنياتي",
    "Your wishlist is empty.": "قائمة أمنياتك فارغة.",
    "Remove from wishlist": "إزالة من المفضلة",
    "My Subscriptions": "اشتراكاتي",
    "New Subscription": "اشتراك جديد",
    "Gift Calendar": "تقويم الهدايا",
    "Active recurring orders": "الطلبات المتكررة النشطة",
    "No subscriptions yet.": "لا توجد اشتراكات بعد.",
    "Create subscription": "إنشاء اشتراك",
    "Frequency": "التكرار",
    "Start date": "تاريخ البدء",
    "Save": "حفظ",
    "Delete": "حذف",
    "Edit": "تعديل",
    "Dashboard": "لوحة التحكم",
    "Orders": "الطلبات",
    "Profile": "الملف الشخصي",
    "Corporate Registration": "تسجيل الشركات",
    "Registration Submitted": "تم إرسال التسجيل",
    "Company name": "اسم الشركة",
    "Password": "كلمة المرور",
    "Confirm password": "تأكيد كلمة المرور",
    "Remember me": "تذكرني",
    "Forgot password?": "نسيت كلمة المرور؟",
    "Sign in": "تسجيل الدخول",
    "Create account": "إنشاء حساب",
    # Corporate / orders
    "Request a Quote": "طلب عرض سعر",
    "Submit Quote Request": "إرسال طلب العرض",
    "Order Tracking": "تتبع الطلب",
    "Track your order": "تتبع طلبك",
    "Current status": "الحالة الحالية",
    "Date": "التاريخ",
    # CMS pages
    "About Us | Story of Flowers": "من نحن | قصة الزهور",
    "Privacy Policy | Story of Flowers": "سياسة الخصوصية | قصة الزهور",
    "Contact Us | Story of Flowers": "اتصل بنا | قصة الزهور",
    "FAQ | Story of Flowers": "الأسئلة الشائعة | قصة الزهور",
    "Blog | Story of Flowers": "المدونة | قصة الزهور",
    "Learn more about Story of Flowers and our mission to deliver flowers and gifts.": "تعرّف أكثر على قصة الزهور ومهمتنا في توصيل الزهور والهدايا.",
    "Read Story of Flower's privacy policy to learn how we collect and use your data.": "اقرأ سياسة خصوصية قصة الزهور لمعرفة كيف نجمع بياناتك ونستخدمها.",
    "Get in touch with Story of Flowers customer support.": "تواصل مع دعم عملاء قصة الزهور.",
    "Frequently asked questions about ordering, delivery, and payments at Story of Flowers.": "أسئلة شائعة حول الطلب والتوصيل والمدفوعات في قصة الزهور.",
    "Read the latest news, tips, and stories from Story of Flowers.": "اقرأ أحدث الأخبار والنصائح والقصص من قصة الزهور.",
    "Name": "الاسم",
    "Subject": "الموضوع",
    "Message": "الرسالة",
    "Send Message": "إرسال الرسالة",
    "Your message has been sent.": "تم إرسال رسالتك.",
    "No FAQ items published yet.": "لا توجد أسئلة شائعة منشورة بعد.",
    "No blog posts yet.": "لا توجد مقالات بعد.",
    "Read more": "اقرأ المزيد",
}


def collect_msgids() -> set[str]:
    # Local import keeps this script runnable as `python scripts/build_locale.py`
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "extract_msgids", ROOT / "scripts" / "extract_msgids.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.collect_msgids()


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def auto_translate_missing(msgids: set[str], existing: dict[str, str]) -> dict[str, str]:
    """Fill missing Arabic strings via GoogleTranslator; skip placeholders-only noise."""
    missing = [m for m in sorted(msgids) if m not in existing or not existing[m]]
    if not missing:
        return existing

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("deep-translator not installed; leaving missing msgstr empty")
        return existing

    translator = GoogleTranslator(source="en", target="ar")
    cache = _load_cache()
    filled = dict(existing)
    for i, msgid in enumerate(missing, 1):
        if msgid in cache and cache[msgid]:
            filled[msgid] = cache[msgid]
            continue
        # Skip very technical / empty
        if not msgid.strip() or msgid.startswith("%(") and msgid.endswith(")s"):
            continue
        try:
            translated = translator.translate(msgid)
            if translated:
                filled[msgid] = translated
                cache[msgid] = translated
        except Exception as exc:
            print(f"  skip translate {msgid!r}: {exc}")
        if i % 20 == 0:
            _save_cache(cache)
            time.sleep(0.3)
    _save_cache(cache)
    return filled


def write_po(lang: str, translations: dict[str, str] | None = None) -> Path:
    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": "floward-clone",
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": lang,
        "MIME-Version": "1.0",
        "Content-Transfer-Encoding": "8bit",
    }
    for msgid in sorted(collect_msgids()):
        msgstr = msgid if translations is None else translations.get(msgid, "")
        if lang == "en":
            msgstr = msgid
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    out = ROOT / "locale" / lang / "LC_MESSAGES" / "django.po"
    out.parent.mkdir(parents=True, exist_ok=True)
    po.save(str(out))
    return out


def compile_mo(po_path: Path) -> Path:
    po = polib.pofile(str(po_path))
    mo_path = po_path.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))
    return mo_path


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    msgids = collect_msgids()
    print(f"Collected {len(msgids)} msgids")

    translations = dict(AR)
    translations = auto_translate_missing(msgids, translations)

    en_po = write_po("en")
    ar_po = write_po("ar", translations)
    en_mo = compile_mo(en_po)
    ar_mo = compile_mo(ar_po)

    ar = polib.pofile(str(ar_po))
    translated = sum(1 for e in ar if e.msgstr)
    print(f"en: {en_po.name} -> {en_mo.name}")
    print(f"ar: {ar_po.name} -> {ar_mo.name}")
    print(f"ar entries={len(ar)} translated={translated} missing={len(ar) - translated}")
    missing = [e.msgid for e in ar if not e.msgstr]
    if missing:
        print("Still missing:")
        for m in missing[:30]:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
