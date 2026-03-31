#!/usr/bin/env python3
"""
Beauty Connect Shop — Collection Description & FAQ Generator + Pusher
Generates rich HTML descriptions with FAQ sections and JSON-LD schema for collections.
Pushes directly to Shopify via GraphQL.

Usage:
    python execution/shopify_collection_descriptions.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SHOPIFY_STORE = os.getenv('SHOPIFY_STORE_URL', '').replace('https://', '').replace('http://', '').strip('/')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_ADMIN_API_TOKEN', '')
API_VERSION = '2024-10'
GRAPHQL_URL = f'https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/graphql.json'
HEADERS = {'X-Shopify-Access-Token': SHOPIFY_TOKEN, 'Content-Type': 'application/json'}


def graphql(query, variables=None):
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    for attempt in range(3):
        resp = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        data = resp.json()
        if 'errors' in data:
            print(f"  GraphQL error: {data['errors']}")
        return data
    return {}


def update_collection(collection_id, description_html, seo_title=None, seo_description=None):
    """Update collection descriptionHtml and SEO fields via collectionUpdate mutation."""
    mutation = """
    mutation collectionUpdate($input: CollectionInput!) {
        collectionUpdate(input: $input) {
            collection { id handle }
            userErrors { field message }
        }
    }
    """
    input_data = {
        'id': collection_id,
        'descriptionHtml': description_html
    }
    if seo_title or seo_description:
        input_data['seo'] = {}
        if seo_title:
            input_data['seo']['title'] = seo_title
        if seo_description:
            input_data['seo']['description'] = seo_description

    variables = {'input': input_data}
    data = graphql(mutation, variables)
    errors = data.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
    if errors:
        print(f"  ERROR updating collection: {errors}")
        return False
    return True


def set_faq_metafield(collection_id, faq_jsonld):
    """Set FAQ JSON-LD as a metafield on the collection."""
    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields { id key namespace }
            userErrors { field message }
        }
    }
    """
    variables = {
        'metafields': [{
            'ownerId': collection_id,
            'namespace': 'custom',
            'key': 'faq_schema',
            'type': 'json',
            'value': faq_jsonld
        }]
    }
    data = graphql(mutation, variables)
    errors = data.get('data', {}).get('metafieldsSet', {}).get('userErrors', [])
    if errors:
        print(f"  ERROR setting metafield: {errors}")
        return False
    return True


# ─── Content Definitions ─────────────────────────────────────────────────────
# Each entry: handle -> (description_html, faq_list)
# FAQ list: [(question, answer), ...]

COLLECTION_CONTENT = {

    "krx": (
        """<div class="collection-seo-content">
<h2>KRX Aesthetics — Professional Korean Dermaceutical Solutions for Clinics</h2>
<p>Beauty Connect Shop is proud to be an authorized Canadian distributor of <strong>KRX Aesthetics</strong>, a leading Korean dermaceutical brand trusted by skincare professionals worldwide. With over 114 professional-grade products, KRX delivers advanced formulations designed specifically for estheticians, dermatology clinics, and medical spas.</p>
<p>KRX Aesthetics combines decades of Korean skincare innovation with rigorous quality standards. Their comprehensive product line includes professional peels, serums, ampoules, masks, and treatment protocols that address a wide range of skin concerns. Each formula is developed using cutting-edge ingredients and delivery systems to help maintain healthy-looking, radiant skin.</p>
<p>Whether you are building a new treatment menu or expanding your existing offerings, KRX provides the tools and protocols to elevate your practice. All products are available at <strong>wholesale pricing</strong> exclusively for licensed professionals in Canada. Enjoy fast nationwide shipping, dedicated B2B support, and access to professional training resources.</p>
<p>Shop the full KRX Aesthetics collection below and discover why thousands of Canadian estheticians trust Beauty Connect Shop as their go-to Korean skincare supplier.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: Is Beauty Connect Shop an authorized KRX Aesthetics distributor in Canada?</strong></summary>
<p>Yes, Beauty Connect Shop is an official authorized distributor of KRX Aesthetics in Canada. We source directly from KRX to ensure product authenticity, proper storage, and full manufacturer support for all professional clients.</p>
</details>
<details>
<summary><strong>Q: Who can purchase KRX Aesthetics products from Beauty Connect Shop?</strong></summary>
<p>KRX Aesthetics products are available exclusively to licensed estheticians, spa owners, dermatology clinics, and skincare professionals. Wholesale pricing and bulk order options are available for qualified businesses across Canada.</p>
</details>
<details>
<summary><strong>Q: What types of professional skincare products does KRX Aesthetics offer?</strong></summary>
<p>KRX Aesthetics offers a comprehensive range including professional peels, serums, ampoules, treatment masks, cleansers, toners, moisturizers, and complete treatment protocols. All products are formulated for professional use in clinical and spa settings.</p>
</details>
<details>
<summary><strong>Q: Does Beauty Connect Shop offer training for KRX Aesthetics products?</strong></summary>
<p>Yes, we provide professional training resources and product education to help estheticians integrate KRX protocols into their practice. Contact our team for information about upcoming training sessions and certification programs.</p>
</details>
<details>
<summary><strong>Q: How fast is shipping for KRX Aesthetics products in Canada?</strong></summary>
<p>We offer fast nationwide shipping across Canada. Most orders are processed within 1-2 business days. Expedited shipping options are available for clinics and spas that need products quickly.</p>
</details>
</div>
</div>""",
        [
            ("Is Beauty Connect Shop an authorized KRX Aesthetics distributor in Canada?",
             "Yes, Beauty Connect Shop is an official authorized distributor of KRX Aesthetics in Canada. We source directly from KRX to ensure product authenticity, proper storage, and full manufacturer support for all professional clients."),
            ("Who can purchase KRX Aesthetics products from Beauty Connect Shop?",
             "KRX Aesthetics products are available exclusively to licensed estheticians, spa owners, dermatology clinics, and skincare professionals. Wholesale pricing and bulk order options are available for qualified businesses across Canada."),
            ("What types of professional skincare products does KRX Aesthetics offer?",
             "KRX Aesthetics offers a comprehensive range including professional peels, serums, ampoules, treatment masks, cleansers, toners, moisturizers, and complete treatment protocols. All products are formulated for professional use in clinical and spa settings."),
            ("Does Beauty Connect Shop offer training for KRX Aesthetics products?",
             "Yes, we provide professional training resources and product education to help estheticians integrate KRX protocols into their practice. Contact our team for information about upcoming training sessions and certification programs."),
            ("How fast is shipping for KRX Aesthetics products in Canada?",
             "We offer fast nationwide shipping across Canada. Most orders are processed within 1-2 business days. Expedited shipping options are available for clinics and spas that need products quickly."),
        ]
    ),

    "zena-cosmetics": (
        """<div class="collection-seo-content">
<h2>Zena Cosmetics — Premium Korean Skincare for Professionals</h2>
<p><strong>Zena Cosmetics</strong> is a distinguished Korean skincare brand offering professional-grade formulations trusted by estheticians and clinic professionals across Canada. Beauty Connect Shop is your authorized wholesale source for the complete Zena Cosmetics line.</p>
<p>Known for their meticulous ingredient selection and advanced formulation techniques, Zena Cosmetics delivers products that help maintain skin hydration, support a healthy complexion, and enhance the overall appearance of skin. Their product range includes targeted serums, nourishing creams, and specialty treatments designed for use in professional spa and clinic environments.</p>
<p>Every Zena Cosmetics product undergoes rigorous quality testing to meet the highest standards expected by skincare professionals. With <strong>wholesale pricing</strong> and fast Canadian shipping, Beauty Connect Shop makes it easy to stock your clinic with these sought-after Korean dermaceutical products.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What makes Zena Cosmetics different from other Korean skincare brands?</strong></summary>
<p>Zena Cosmetics focuses on professional-grade formulations developed specifically for use in clinical and spa settings. Their products feature advanced ingredient combinations and concentrations designed to meet the high standards of licensed estheticians.</p>
</details>
<details>
<summary><strong>Q: Can I purchase Zena Cosmetics at wholesale prices?</strong></summary>
<p>Yes, Beauty Connect Shop offers exclusive wholesale pricing on all Zena Cosmetics products for licensed estheticians, spa owners, and clinic professionals in Canada. Contact us for bulk order pricing and volume discounts.</p>
</details>
<details>
<summary><strong>Q: Are Zena Cosmetics products suitable for sensitive skin types?</strong></summary>
<p>Zena Cosmetics formulations are developed with professional use in mind and are suitable for a variety of skin types. We recommend consulting with a licensed skincare professional for personalized product recommendations based on individual skin needs.</p>
</details>
</div>
</div>""",
        [
            ("What makes Zena Cosmetics different from other Korean skincare brands?",
             "Zena Cosmetics focuses on professional-grade formulations developed specifically for use in clinical and spa settings. Their products feature advanced ingredient combinations and concentrations designed to meet the high standards of licensed estheticians."),
            ("Can I purchase Zena Cosmetics at wholesale prices?",
             "Yes, Beauty Connect Shop offers exclusive wholesale pricing on all Zena Cosmetics products for licensed estheticians, spa owners, and clinic professionals in Canada. Contact us for bulk order pricing and volume discounts."),
            ("Are Zena Cosmetics products suitable for sensitive skin types?",
             "Zena Cosmetics formulations are developed with professional use in mind and are suitable for a variety of skin types. We recommend consulting with a licensed skincare professional for personalized product recommendations based on individual skin needs."),
        ]
    ),

    "corthe": (
        """<div class="collection-seo-content">
<h2>Corthe — Advanced Korean Dermaceutical Brand for Skincare Professionals</h2>
<p><strong>Corthe</strong> is one of Korea's most respected dermaceutical brands, offering a comprehensive line of over 57 professional skincare products. Beauty Connect Shop is the authorized Canadian distributor, bringing Corthe's advanced formulations directly to estheticians, medical spas, and dermatology clinics nationwide.</p>
<p>Corthe's product philosophy centres on science-driven skincare that delivers visible results. Their extensive range includes professional cleansers, toners, serums, moisturizers, masks, and specialized treatment products — all formulated with carefully selected ingredients to support skin hydration, improve skin texture, and enhance overall complexion appearance.</p>
<p>Designed exclusively for professional use, Corthe products come with detailed protocols that integrate seamlessly into existing treatment menus. Whether you specialize in hydration facials, brightening treatments, or comprehensive skin maintenance programs, Corthe provides the professional tools you need.</p>
<p>Order at <strong>wholesale prices</strong> with fast shipping across Canada. Beauty Connect Shop provides dedicated B2B support to help you build your Corthe treatment menu.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What is Corthe and why do Canadian estheticians trust this brand?</strong></summary>
<p>Corthe is a leading Korean dermaceutical brand known for its science-driven approach to professional skincare. Canadian estheticians trust Corthe for its consistent quality, comprehensive treatment protocols, and visible results that keep clients coming back.</p>
</details>
<details>
<summary><strong>Q: How many Corthe products are available at Beauty Connect Shop?</strong></summary>
<p>Beauty Connect Shop carries the full Corthe line of over 57 professional-grade products, including cleansers, toners, serums, moisturizers, masks, and specialty treatment items. All products are available at wholesale pricing for licensed professionals.</p>
</details>
<details>
<summary><strong>Q: Does Corthe offer complete treatment protocols for clinics?</strong></summary>
<p>Yes, Corthe provides detailed professional treatment protocols that integrate multiple products into cohesive facial treatment programs. These protocols are designed to help estheticians deliver consistent, high-quality results in their practice.</p>
</details>
<details>
<summary><strong>Q: Can I get Corthe products shipped anywhere in Canada?</strong></summary>
<p>Absolutely. Beauty Connect Shop ships Corthe products nationwide across Canada. We offer fast processing times and reliable delivery so your clinic stays fully stocked with the Korean dermaceutical products you need.</p>
</details>
</div>
</div>""",
        [
            ("What is Corthe and why do Canadian estheticians trust this brand?",
             "Corthe is a leading Korean dermaceutical brand known for its science-driven approach to professional skincare. Canadian estheticians trust Corthe for its consistent quality, comprehensive treatment protocols, and visible results that keep clients coming back."),
            ("How many Corthe products are available at Beauty Connect Shop?",
             "Beauty Connect Shop carries the full Corthe line of over 57 professional-grade products, including cleansers, toners, serums, moisturizers, masks, and specialty treatment items. All products are available at wholesale pricing for licensed professionals."),
            ("Does Corthe offer complete treatment protocols for clinics?",
             "Yes, Corthe provides detailed professional treatment protocols that integrate multiple products into cohesive facial treatment programs. These protocols are designed to help estheticians deliver consistent, high-quality results in their practice."),
            ("Can I get Corthe products shipped anywhere in Canada?",
             "Absolutely. Beauty Connect Shop ships Corthe products nationwide across Canada. We offer fast processing times and reliable delivery so your clinic stays fully stocked with the Korean dermaceutical products you need."),
        ]
    ),

    "bundle-kits": (
        """<div class="collection-seo-content">
<h2>Professional Skincare Bundle Kits — Curated Korean Dermaceutical Sets</h2>
<p>Save more and simplify your ordering with our <strong>professional skincare bundle kits</strong>. Each kit is carefully curated by Beauty Connect Shop to provide estheticians, spa owners, and clinic professionals with complementary Korean dermaceutical products that work together for optimal results.</p>
<p>Our bundle kits feature products from top Korean brands like KRX Aesthetics and Corthe, grouped into treatment-ready combinations. Whether you need a complete facial protocol kit, a hydration treatment bundle, or a starter set for a new service offering, our curated kits take the guesswork out of product selection.</p>
<p>Every bundle kit comes at <strong>special wholesale pricing</strong> — offering even greater savings compared to purchasing products individually. This makes it easy for clinics to stock up on the professional-grade Korean skincare products they use most, while keeping inventory costs manageable.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What is included in Beauty Connect Shop's professional bundle kits?</strong></summary>
<p>Each bundle kit contains a curated selection of complementary Korean dermaceutical products designed to work together. Kits may include cleansers, serums, masks, moisturizers, and treatment products grouped by skin concern or treatment protocol.</p>
</details>
<details>
<summary><strong>Q: Are bundle kits more affordable than buying products separately?</strong></summary>
<p>Yes, our bundle kits are priced at a discount compared to purchasing each product individually. This offers significant savings for clinics and spas looking to stock professional-grade Korean skincare products at the best wholesale value.</p>
</details>
<details>
<summary><strong>Q: Can I customize a bundle kit for my clinic's specific needs?</strong></summary>
<p>While our pre-curated kits cover the most popular treatment combinations, you can contact our B2B team to discuss custom bundle options tailored to your clinic's specific treatment menu and product preferences.</p>
</details>
</div>
</div>""",
        [
            ("What is included in Beauty Connect Shop's professional bundle kits?",
             "Each bundle kit contains a curated selection of complementary Korean dermaceutical products designed to work together. Kits may include cleansers, serums, masks, moisturizers, and treatment products grouped by skin concern or treatment protocol."),
            ("Are bundle kits more affordable than buying products separately?",
             "Yes, our bundle kits are priced at a discount compared to purchasing each product individually. This offers significant savings for clinics and spas looking to stock professional-grade Korean skincare products at the best wholesale value."),
            ("Can I customize a bundle kit for my clinic's specific needs?",
             "While our pre-curated kits cover the most popular treatment combinations, you can contact our B2B team to discuss custom bundle options tailored to your clinic's specific treatment menu and product preferences."),
        ]
    ),

    "teeth-whitening-supplies": (
        """<div class="collection-seo-content">
<h2>Professional Teeth Whitening Supplies — Wholesale for Clinics in Canada</h2>
<p>Expand your service menu with <strong>professional teeth whitening supplies</strong> from Beauty Connect Shop. We carry a curated selection of whitening products designed for use by trained professionals in spa and clinic settings across Canada.</p>
<p>Our teeth whitening supplies include professional-grade whitening gels, LED accelerator devices, application accessories, and client aftercare products. Each product is sourced from reputable manufacturers and meets Canadian standards for professional cosmetic use.</p>
<p>Adding teeth whitening to your service offerings is one of the fastest ways to increase per-client revenue. With our <strong>wholesale pricing</strong> and fast Canadian shipping, stocking up on supplies is simple and cost-effective. Contact our team for volume discounts and starter kit recommendations.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: Are these teeth whitening products designed for professional use?</strong></summary>
<p>Yes, all teeth whitening supplies at Beauty Connect Shop are professional-grade products designed for use by trained practitioners in clinic, spa, and salon settings. They are not intended for unsupervised consumer use.</p>
</details>
<details>
<summary><strong>Q: Can estheticians offer teeth whitening services in Canada?</strong></summary>
<p>Regulations vary by province. Many Canadian provinces allow trained estheticians and spa professionals to offer cosmetic teeth whitening services. We recommend checking your provincial regulations and obtaining any required certifications.</p>
</details>
<details>
<summary><strong>Q: Does Beauty Connect Shop offer teeth whitening starter kits?</strong></summary>
<p>Yes, we offer starter kits and bundle options to help professionals launch teeth whitening services. Contact our B2B team for recommendations based on your practice size and expected client volume.</p>
</details>
</div>
</div>""",
        [
            ("Are these teeth whitening products designed for professional use?",
             "Yes, all teeth whitening supplies at Beauty Connect Shop are professional-grade products designed for use by trained practitioners in clinic, spa, and salon settings. They are not intended for unsupervised consumer use."),
            ("Can estheticians offer teeth whitening services in Canada?",
             "Regulations vary by province. Many Canadian provinces allow trained estheticians and spa professionals to offer cosmetic teeth whitening services. We recommend checking your provincial regulations and obtaining any required certifications."),
            ("Does Beauty Connect Shop offer teeth whitening starter kits?",
             "Yes, we offer starter kits and bundle options to help professionals launch teeth whitening services. Contact our B2B team for recommendations based on your practice size and expected client volume."),
        ]
    ),

    "lash-supplies": (
        """<div class="collection-seo-content">
<h2>Professional Lash Supplies — Wholesale Eyelash Extension Products in Canada</h2>
<p>Beauty Connect Shop carries a premium selection of <strong>professional lash supplies</strong> for estheticians and lash technicians across Canada. Our collection includes everything you need to deliver flawless eyelash extension services in your salon, spa, or clinic.</p>
<p>Browse professional-grade lash adhesives, individual lash trays, lash removal solutions, application tools, and aftercare products. All products are sourced from trusted manufacturers known for consistent quality and salon-grade performance.</p>
<p>Whether you are an experienced lash artist or expanding your service menu, our wholesale pricing makes it easy to keep your lash station fully stocked. Enjoy <strong>fast shipping across Canada</strong> and dedicated support from our B2B team.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of lash supplies does Beauty Connect Shop carry?</strong></summary>
<p>We carry a complete range of professional lash supplies including individual lash trays in various lengths and curls, professional adhesives, removers, primers, application tweezers, eye pads, and client aftercare products.</p>
</details>
<details>
<summary><strong>Q: Are these lash products suitable for salon and clinic use?</strong></summary>
<p>Yes, all lash supplies in this collection are professional-grade products designed specifically for use by trained lash technicians and estheticians in salon, spa, and clinic environments.</p>
</details>
<details>
<summary><strong>Q: Does Beauty Connect Shop offer wholesale pricing on lash supplies?</strong></summary>
<p>Absolutely. All lash supplies are available at competitive wholesale pricing for licensed professionals. Contact our team for volume discounts and to set up a wholesale account for your business.</p>
</details>
</div>
</div>""",
        [
            ("What types of lash supplies does Beauty Connect Shop carry?",
             "We carry a complete range of professional lash supplies including individual lash trays in various lengths and curls, professional adhesives, removers, primers, application tweezers, eye pads, and client aftercare products."),
            ("Are these lash products suitable for salon and clinic use?",
             "Yes, all lash supplies in this collection are professional-grade products designed specifically for use by trained lash technicians and estheticians in salon, spa, and clinic environments."),
            ("Does Beauty Connect Shop offer wholesale pricing on lash supplies?",
             "Absolutely. All lash supplies are available at competitive wholesale pricing for licensed professionals. Contact our team for volume discounts and to set up a wholesale account for your business."),
        ]
    ),

    "all-products": (
        """<div class="collection-seo-content">
<h2>All Products — Complete Korean Dermaceutical Catalog for Professionals</h2>
<p>Browse the <strong>complete Beauty Connect Shop catalog</strong> featuring over 200 professional-grade Korean dermaceutical products. As Canada's trusted B2B supplier for estheticians, spa owners, and clinic professionals, we bring you the best of Korean skincare innovation at wholesale prices.</p>
<p>Our extensive product catalog includes professional cleansers, toners, essences, serums, ampoules, treatment masks, peels, moisturizers, eye care, body care, and specialty treatment products. We carry top Korean brands including KRX Aesthetics, Corthe, and Zena Cosmetics — all available exclusively for licensed skincare professionals.</p>
<p>Every product in our catalog is selected for its professional-grade quality, advanced formulation, and proven performance in clinical settings. Use the filters to browse by product type, brand, skin concern, or treatment category to find exactly what your clinic needs.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: How many products does Beauty Connect Shop carry?</strong></summary>
<p>Beauty Connect Shop carries over 200 professional Korean dermaceutical products spanning multiple brands and categories. Our catalog is continuously updated with new arrivals and seasonal collections.</p>
</details>
<details>
<summary><strong>Q: Is Beauty Connect Shop a wholesale-only supplier?</strong></summary>
<p>Beauty Connect Shop primarily serves licensed estheticians, spa owners, and clinic professionals with wholesale pricing. We are dedicated to supporting the professional beauty industry across Canada.</p>
</details>
<details>
<summary><strong>Q: What Korean skincare brands are available at Beauty Connect Shop?</strong></summary>
<p>We carry leading Korean dermaceutical brands including KRX Aesthetics, Corthe, and Zena Cosmetics. Each brand is carefully selected for its professional-grade quality and suitability for clinic and spa use.</p>
</details>
</div>
</div>""",
        [
            ("How many products does Beauty Connect Shop carry?",
             "Beauty Connect Shop carries over 200 professional Korean dermaceutical products spanning multiple brands and categories. Our catalog is continuously updated with new arrivals and seasonal collections."),
            ("Is Beauty Connect Shop a wholesale-only supplier?",
             "Beauty Connect Shop primarily serves licensed estheticians, spa owners, and clinic professionals with wholesale pricing. We are dedicated to supporting the professional beauty industry across Canada."),
            ("What Korean skincare brands are available at Beauty Connect Shop?",
             "We carry leading Korean dermaceutical brands including KRX Aesthetics, Corthe, and Zena Cosmetics. Each brand is carefully selected for its professional-grade quality and suitability for clinic and spa use."),
        ]
    ),

    "cleansers": (
        """<div class="collection-seo-content">
<h2>Professional Korean Cleansers — Wholesale Skincare Cleansing Products</h2>
<p>A thorough cleanse is the foundation of every effective skincare treatment. Beauty Connect Shop's <strong>professional Korean cleansers</strong> collection features over 20 premium cleansing products from top dermaceutical brands, formulated specifically for use by estheticians and skincare professionals.</p>
<p>Our cleansing range includes gentle foam cleansers, oil-based cleansers for double-cleansing protocols, enzyme cleansing powders, micellar waters, and deep-cleansing gel formulations. Each product is designed to effectively remove impurities, makeup residue, and excess sebum while maintaining the skin's natural moisture balance.</p>
<p>These professional-grade cleansers serve as the essential first step in Korean skincare treatment protocols. Available at <strong>wholesale pricing</strong> for clinics, spas, and licensed estheticians across Canada with fast nationwide shipping.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of professional cleansers are available?</strong></summary>
<p>Our collection includes foam cleansers, oil cleansers, enzyme powders, micellar waters, and gel cleansers. Each type is suited for different treatment protocols and skin types, giving professionals flexibility in their facial services.</p>
</details>
<details>
<summary><strong>Q: Are these cleansers suitable for use in professional facial treatments?</strong></summary>
<p>Yes, all cleansers in this collection are professional-grade formulations designed for use in spa, clinic, and salon settings. They are ideal for the cleansing step of Korean skincare facial protocols.</p>
</details>
<details>
<summary><strong>Q: How do Korean cleansers differ from standard skincare cleansers?</strong></summary>
<p>Korean dermaceutical cleansers typically feature advanced formulations with carefully selected ingredients that effectively cleanse while helping to maintain skin hydration. They are designed for the double-cleansing method popular in professional Korean skincare routines.</p>
</details>
</div>
</div>""",
        [
            ("What types of professional cleansers are available?",
             "Our collection includes foam cleansers, oil cleansers, enzyme powders, micellar waters, and gel cleansers. Each type is suited for different treatment protocols and skin types, giving professionals flexibility in their facial services."),
            ("Are these cleansers suitable for use in professional facial treatments?",
             "Yes, all cleansers in this collection are professional-grade formulations designed for use in spa, clinic, and salon settings. They are ideal for the cleansing step of Korean skincare facial protocols."),
            ("How do Korean cleansers differ from standard skincare cleansers?",
             "Korean dermaceutical cleansers typically feature advanced formulations with carefully selected ingredients that effectively cleanse while helping to maintain skin hydration. They are designed for the double-cleansing method popular in professional Korean skincare routines."),
        ]
    ),

    "masks": (
        """<div class="collection-seo-content">
<h2>Professional Korean Face Masks — Wholesale Treatment Masks for Clinics</h2>
<p>Elevate your facial treatment menu with our <strong>professional Korean face masks</strong> collection. With 40 premium mask products, Beauty Connect Shop offers one of Canada's largest selections of dermaceutical-grade treatment masks for estheticians and clinic professionals.</p>
<p>Our collection includes hydrating sheet masks, collagen modeling masks, rubber masks, gel masks, clay masks, and specialty treatment masks. These professional masks are formulated with concentrated active ingredients to deliver intensive hydration, improve skin texture, and enhance overall complexion radiance during facial treatments.</p>
<p>Korean treatment masks are a cornerstone of professional facial protocols, providing clients with a luxurious, results-driven experience. Stock your clinic at <strong>wholesale prices</strong> and enjoy fast shipping across Canada.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of professional face masks does Beauty Connect Shop carry?</strong></summary>
<p>We carry sheet masks, collagen modeling masks, rubber masks, gel masks, clay masks, and specialty treatment masks. Each type serves a different purpose in professional facial protocols, from intensive hydration to deep cleansing.</p>
</details>
<details>
<summary><strong>Q: How are professional Korean masks different from retail masks?</strong></summary>
<p>Professional Korean masks feature higher concentrations of key ingredients and are designed for use within structured treatment protocols. They are formulated to deliver more intensive results when applied by trained estheticians in a professional setting.</p>
</details>
<details>
<summary><strong>Q: Can I use these masks in combination with other professional treatments?</strong></summary>
<p>Absolutely. Professional Korean masks are designed to integrate seamlessly into multi-step facial protocols. They pair well with professional serums, ampoules, and other treatment products to enhance overall facial treatment results.</p>
</details>
<details>
<summary><strong>Q: Are bulk orders available for popular mask products?</strong></summary>
<p>Yes, Beauty Connect Shop offers wholesale pricing and bulk order options on all mask products. Contact our B2B team for volume discounts tailored to your clinic's usage needs.</p>
</details>
</div>
</div>""",
        [
            ("What types of professional face masks does Beauty Connect Shop carry?",
             "We carry sheet masks, collagen modeling masks, rubber masks, gel masks, clay masks, and specialty treatment masks. Each type serves a different purpose in professional facial protocols, from intensive hydration to deep cleansing."),
            ("How are professional Korean masks different from retail masks?",
             "Professional Korean masks feature higher concentrations of key ingredients and are designed for use within structured treatment protocols. They are formulated to deliver more intensive results when applied by trained estheticians in a professional setting."),
            ("Can I use these masks in combination with other professional treatments?",
             "Absolutely. Professional Korean masks are designed to integrate seamlessly into multi-step facial protocols. They pair well with professional serums, ampoules, and other treatment products to enhance overall facial treatment results."),
            ("Are bulk orders available for popular mask products?",
             "Yes, Beauty Connect Shop offers wholesale pricing and bulk order options on all mask products. Contact our B2B team for volume discounts tailored to your clinic's usage needs."),
        ]
    ),

    "peels": (
        """<div class="collection-seo-content">
<h2>Professional Korean Peels — Wholesale Chemical Peels for Estheticians</h2>
<p>Beauty Connect Shop's <strong>professional Korean peels</strong> collection features 17 advanced peeling products designed for use by trained estheticians and skincare professionals. These dermaceutical-grade peels are formulated to support skin renewal, improve texture, and reveal a brighter, more even-looking complexion.</p>
<p>Our peeling collection includes gentle enzyme peels, multi-acid solutions, professional-strength exfoliation treatments, and peel preparation and aftercare products. Each product comes with clear professional usage guidelines to help estheticians deliver safe, consistent results across a range of skin types.</p>
<p>Professional peels remain one of the most requested treatments in spas and clinics. Keep your peel station stocked with trusted Korean dermaceutical formulations at <strong>wholesale prices</strong>, shipped fast across Canada.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of professional peels are available at Beauty Connect Shop?</strong></summary>
<p>We offer a range of professional peels including enzyme peels, multi-acid peels, and progressive peel systems. Our collection also includes pre-peel preparation products and post-peel aftercare essentials for complete treatment protocols.</p>
</details>
<details>
<summary><strong>Q: Are these peels suitable for all skin types?</strong></summary>
<p>Our professional peel collection includes options suitable for various skin types and concerns. Licensed estheticians should assess each client individually and select the appropriate peel strength and type based on professional skin analysis.</p>
</details>
<details>
<summary><strong>Q: Do the professional peels come with usage protocols?</strong></summary>
<p>Yes, all professional peels include detailed usage guidelines and protocols. Beauty Connect Shop also offers educational resources to help estheticians safely integrate these Korean peel treatments into their service menu.</p>
</details>
</div>
</div>""",
        [
            ("What types of professional peels are available at Beauty Connect Shop?",
             "We offer a range of professional peels including enzyme peels, multi-acid peels, and progressive peel systems. Our collection also includes pre-peel preparation products and post-peel aftercare essentials for complete treatment protocols."),
            ("Are these peels suitable for all skin types?",
             "Our professional peel collection includes options suitable for various skin types and concerns. Licensed estheticians should assess each client individually and select the appropriate peel strength and type based on professional skin analysis."),
            ("Do the professional peels come with usage protocols?",
             "Yes, all professional peels include detailed usage guidelines and protocols. Beauty Connect Shop also offers educational resources to help estheticians safely integrate these Korean peel treatments into their service menu."),
        ]
    ),

    "serums-ampoules": (
        """<div class="collection-seo-content">
<h2>Professional Korean Serums &amp; Ampoules — Concentrated Skincare for Clinics</h2>
<p>Discover our curated collection of <strong>professional Korean serums and ampoules</strong> — the powerhouse step in any advanced skincare protocol. With over 30 concentrated formulations, Beauty Connect Shop provides estheticians and clinic professionals with some of Korea's most advanced targeted skincare solutions.</p>
<p>Our serum and ampoule collection includes hydrating hyaluronic acid formulas, brightening vitamin C serums, nourishing peptide ampoules, calming centella formulations, and multi-functional treatment concentrates. Each product delivers concentrated ingredients designed to address specific skin concerns and enhance overall facial treatment results.</p>
<p>Professional serums and ampoules are essential for creating customized treatment experiences that keep clients coming back. Stock your clinic with the best Korean dermaceutical concentrates at <strong>wholesale prices</strong> with fast Canadian shipping.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What is the difference between a serum and an ampoule?</strong></summary>
<p>Serums are lightweight, concentrated formulations designed for daily professional use. Ampoules are typically even more concentrated, offering intensive targeted support often used as a booster within professional facial treatments for enhanced results.</p>
</details>
<details>
<summary><strong>Q: How do professionals use Korean serums in facial treatments?</strong></summary>
<p>Professional Korean serums are typically applied after cleansing and toning, before masking or moisturizing. Estheticians select specific serums based on the client's skin needs, layering them for customized treatment protocols.</p>
</details>
<details>
<summary><strong>Q: Are these serums and ampoules available at wholesale pricing?</strong></summary>
<p>Yes, all serums and ampoules in this collection are available at wholesale pricing for licensed estheticians, spa owners, and clinic professionals across Canada. Volume discounts are also available for larger orders.</p>
</details>
<details>
<summary><strong>Q: Which serum ingredients are most popular among Canadian estheticians?</strong></summary>
<p>Hyaluronic acid, vitamin C, peptide complexes, niacinamide, and centella asiatica are among the most popular serum ingredients requested by Canadian estheticians. Our collection features Korean formulations showcasing these and other sought-after ingredients.</p>
</details>
</div>
</div>""",
        [
            ("What is the difference between a serum and an ampoule?",
             "Serums are lightweight, concentrated formulations designed for daily professional use. Ampoules are typically even more concentrated, offering intensive targeted support often used as a booster within professional facial treatments for enhanced results."),
            ("How do professionals use Korean serums in facial treatments?",
             "Professional Korean serums are typically applied after cleansing and toning, before masking or moisturizing. Estheticians select specific serums based on the client's skin needs, layering them for customized treatment protocols."),
            ("Are these serums and ampoules available at wholesale pricing?",
             "Yes, all serums and ampoules in this collection are available at wholesale pricing for licensed estheticians, spa owners, and clinic professionals across Canada. Volume discounts are also available for larger orders."),
            ("Which serum ingredients are most popular among Canadian estheticians?",
             "Hyaluronic acid, vitamin C, peptide complexes, niacinamide, and centella asiatica are among the most popular serum ingredients requested by Canadian estheticians. Our collection features Korean formulations showcasing these and other sought-after ingredients."),
        ]
    ),

    "toners-essences": (
        """<div class="collection-seo-content">
<h2>Professional Korean Toners &amp; Essences — Wholesale Skincare Prep Products</h2>
<p>Prepare skin for optimal product absorption with our <strong>professional Korean toners and essences</strong>. This collection features 19 expertly formulated products that serve as the essential prep step in Korean skincare treatment protocols used by estheticians across Canada.</p>
<p>Our toner and essence range includes hydrating toners, pH-balancing formulas, first treatment essences, fermented essences, and exfoliating toner pads. These products help restore skin's pH balance after cleansing, boost hydration levels, and prime the skin to receive subsequent treatment products more effectively.</p>
<p>In professional Korean skincare protocols, the toning step is critical for maximizing the efficacy of serums, ampoules, and masks that follow. Stock your clinic with these professional-grade prep products at <strong>wholesale prices</strong>.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What is the difference between a toner and an essence in Korean skincare?</strong></summary>
<p>Toners primarily balance skin's pH and remove residual impurities after cleansing. Essences are slightly more concentrated, delivering a first layer of hydration and active ingredients to prepare skin for subsequent treatment steps.</p>
</details>
<details>
<summary><strong>Q: Why are toners important in professional facial treatments?</strong></summary>
<p>Professional toners restore optimal skin pH after cleansing, which helps subsequent products absorb more effectively. This step maximizes the performance of serums, ampoules, and masks applied during the treatment.</p>
</details>
<details>
<summary><strong>Q: Are Korean toners and essences suitable for all skin types?</strong></summary>
<p>Our collection includes formulations suitable for various skin types. Licensed estheticians can select the most appropriate toner or essence based on professional skin analysis to customize each client's treatment protocol.</p>
</details>
</div>
</div>""",
        [
            ("What is the difference between a toner and an essence in Korean skincare?",
             "Toners primarily balance skin's pH and remove residual impurities after cleansing. Essences are slightly more concentrated, delivering a first layer of hydration and active ingredients to prepare skin for subsequent treatment steps."),
            ("Why are toners important in professional facial treatments?",
             "Professional toners restore optimal skin pH after cleansing, which helps subsequent products absorb more effectively. This step maximizes the performance of serums, ampoules, and masks applied during the treatment."),
            ("Are Korean toners and essences suitable for all skin types?",
             "Our collection includes formulations suitable for various skin types. Licensed estheticians can select the most appropriate toner or essence based on professional skin analysis to customize each client's treatment protocol."),
        ]
    ),

    "treatments": (
        """<div class="collection-seo-content">
<h2>Professional Korean Skincare Treatments — Advanced Solutions for Estheticians</h2>
<p>Beauty Connect Shop's <strong>professional treatments</strong> collection is our largest category with over 70 advanced Korean dermaceutical products designed for clinical and spa use. This comprehensive range gives estheticians and skincare professionals everything they need to deliver results-driven facial treatments.</p>
<p>Our treatments collection encompasses specialized products that go beyond daily skincare routines — including intensive treatment concentrates, professional boosters, targeted spot solutions, advanced complexion enhancers, and multi-step treatment systems. Each product is formulated with professional-strength ingredients to deliver visible improvements in skin appearance and texture.</p>
<p>Build a comprehensive treatment menu that keeps your clients coming back. From hydration-focused protocols to advanced brightening and skin renewal treatments, this collection provides the professional tools you need. All available at <strong>wholesale pricing</strong> with fast shipping across Canada.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What makes the treatments collection different from other product categories?</strong></summary>
<p>The treatments collection features specialized, professional-strength products designed for targeted use during facial services. These go beyond basic cleansing and moisturizing to deliver intensive, focused results that clients can see and feel after each session.</p>
</details>
<details>
<summary><strong>Q: Are these treatment products suitable for use by all estheticians?</strong></summary>
<p>Yes, while some advanced treatments may require specific training, most products in this collection are designed for use by licensed estheticians. Beauty Connect Shop offers product education and protocol guidance to help professionals integrate new treatments confidently.</p>
</details>
<details>
<summary><strong>Q: How can I build a treatment menu using these products?</strong></summary>
<p>Our B2B team can help you design a treatment menu using products from this collection. We offer consultation on product pairing, treatment protocols, and pricing strategies to help your clinic maximize revenue from Korean skincare services.</p>
</details>
<details>
<summary><strong>Q: Do you offer training on professional Korean skincare treatments?</strong></summary>
<p>Yes, Beauty Connect Shop provides product training and educational resources for estheticians. Contact our team to learn about upcoming training sessions, webinars, and certification programs related to professional Korean skincare treatments.</p>
</details>
</div>
</div>""",
        [
            ("What makes the treatments collection different from other product categories?",
             "The treatments collection features specialized, professional-strength products designed for targeted use during facial services. These go beyond basic cleansing and moisturizing to deliver intensive, focused results that clients can see and feel after each session."),
            ("Are these treatment products suitable for use by all estheticians?",
             "Yes, while some advanced treatments may require specific training, most products in this collection are designed for use by licensed estheticians. Beauty Connect Shop offers product education and protocol guidance to help professionals integrate new treatments confidently."),
            ("How can I build a treatment menu using these products?",
             "Our B2B team can help you design a treatment menu using products from this collection. We offer consultation on product pairing, treatment protocols, and pricing strategies to help your clinic maximize revenue from Korean skincare services."),
            ("Do you offer training on professional Korean skincare treatments?",
             "Yes, Beauty Connect Shop provides product training and educational resources for estheticians. Contact our team to learn about upcoming training sessions, webinars, and certification programs related to professional Korean skincare treatments."),
        ]
    ),

    "moisturizers": (
        """<div class="collection-seo-content">
<h2>Professional Korean Moisturizers — Wholesale Hydration Products for Clinics</h2>
<p>Complete every facial treatment with our <strong>professional Korean moisturizers</strong> collection. Featuring 24 premium hydration products, this collection gives estheticians and clinic professionals access to Korea's most advanced moisturizing formulations at wholesale prices.</p>
<p>Our moisturizer range includes lightweight gel creams, rich barrier creams, water-based hydrators, sleeping masks, and specialized moisturizing treatments. Each product is formulated to lock in hydration, support the skin's moisture barrier, and leave skin looking plump, smooth, and radiant after professional treatments.</p>
<p>The moisturizing step is the finishing touch that seals in the benefits of your entire treatment protocol. Ensure your clients leave with perfectly hydrated, comfortable skin by stocking these <strong>professional-grade Korean moisturizers</strong> at wholesale prices.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of professional moisturizers are available in this collection?</strong></summary>
<p>Our collection includes gel creams, barrier creams, water-based hydrators, sleeping masks, and specialty moisturizing treatments. Each type is designed for different skin needs and treatment protocols in professional settings.</p>
</details>
<details>
<summary><strong>Q: How do Korean moisturizers support professional facial treatments?</strong></summary>
<p>Korean moisturizers serve as the final sealing step in professional facial protocols, locking in the benefits of cleansers, toners, serums, and masks applied during the treatment. They help maintain skin hydration and comfort long after the client leaves the clinic.</p>
</details>
<details>
<summary><strong>Q: Are these moisturizers suitable for use on all skin types?</strong></summary>
<p>Yes, our collection includes moisturizers formulated for various skin types from oily to dry. Licensed estheticians can select the most appropriate moisturizer based on each client's skin analysis and the specific treatment performed.</p>
</details>
</div>
</div>""",
        [
            ("What types of professional moisturizers are available in this collection?",
             "Our collection includes gel creams, barrier creams, water-based hydrators, sleeping masks, and specialty moisturizing treatments. Each type is designed for different skin needs and treatment protocols in professional settings."),
            ("How do Korean moisturizers support professional facial treatments?",
             "Korean moisturizers serve as the final sealing step in professional facial protocols, locking in the benefits of cleansers, toners, serums, and masks applied during the treatment. They help maintain skin hydration and comfort long after the client leaves the clinic."),
            ("Are these moisturizers suitable for use on all skin types?",
             "Yes, our collection includes moisturizers formulated for various skin types from oily to dry. Licensed estheticians can select the most appropriate moisturizer based on each client's skin analysis and the specific treatment performed."),
        ]
    ),

    "hydrofacial-solutions": (
        """<div class="collection-seo-content">
<h2>Hydrofacial Solutions — Professional Hydrodermabrasion Products Wholesale</h2>
<p>Power your hydrofacial machine with <strong>professional hydrofacial solutions</strong> from Beauty Connect Shop. Our hydrofacial solutions are specially formulated for use with hydrodermabrasion devices in spa and clinic settings across Canada.</p>
<p>These concentrated solutions are designed to cleanse, exfoliate, and deliver hydration during hydrofacial treatments — one of the most popular and in-demand facial services in the professional skincare industry. Each solution is formulated with professional-grade ingredients to ensure optimal performance with your hydrofacial equipment.</p>
<p>Keep your hydrofacial station running smoothly with reliable, high-quality solutions at <strong>wholesale pricing</strong>. Beauty Connect Shop offers fast shipping across Canada so your clinic never runs out of supplies.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: Are these solutions compatible with all hydrofacial machines?</strong></summary>
<p>Our hydrofacial solutions are formulated to be compatible with most standard hydrodermabrasion devices. We recommend checking your machine's specifications or contacting our team for compatibility confirmation before ordering.</p>
</details>
<details>
<summary><strong>Q: How often should hydrofacial solutions be replaced?</strong></summary>
<p>Usage depends on your client volume and treatment frequency. Most clinics reorder monthly. Beauty Connect Shop offers wholesale pricing and recurring order options to help you maintain consistent supply for your practice.</p>
</details>
<details>
<summary><strong>Q: Can I order hydrofacial solutions in bulk at a discount?</strong></summary>
<p>Yes, we offer volume discounts on hydrofacial solutions for busy clinics. Contact our B2B team for bulk pricing and to set up a recurring order schedule that matches your clinic's demand.</p>
</details>
</div>
</div>""",
        [
            ("Are these solutions compatible with all hydrofacial machines?",
             "Our hydrofacial solutions are formulated to be compatible with most standard hydrodermabrasion devices. We recommend checking your machine's specifications or contacting our team for compatibility confirmation before ordering."),
            ("How often should hydrofacial solutions be replaced?",
             "Usage depends on your client volume and treatment frequency. Most clinics reorder monthly. Beauty Connect Shop offers wholesale pricing and recurring order options to help you maintain consistent supply for your practice."),
            ("Can I order hydrofacial solutions in bulk at a discount?",
             "Yes, we offer volume discounts on hydrofacial solutions for busy clinics. Contact our B2B team for bulk pricing and to set up a recurring order schedule that matches your clinic's demand."),
        ]
    ),

    "eye-neck-care": (
        """<div class="collection-seo-content">
<h2>Professional Eye &amp; Neck Care — Korean Dermaceutical Solutions Wholesale</h2>
<p>Address the delicate eye and neck area with our <strong>professional Korean eye and neck care</strong> products. This specialized collection features targeted formulations designed to help maintain the appearance of these sensitive areas during professional facial treatments.</p>
<p>Our eye and neck care range includes concentrated eye creams, peptide-rich eye patches, firming neck creams, and specialty treatment masks for the periorbital and cervical areas. Each product is formulated with gentle yet effective ingredients suitable for the thinner, more delicate skin around the eyes and neck.</p>
<p>Adding eye and neck care as an add-on service is an excellent way to increase per-treatment revenue in your clinic. Stock these <strong>professional-grade products</strong> at wholesale prices from Beauty Connect Shop.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: Why do the eye and neck areas need specialized products?</strong></summary>
<p>The skin around the eyes and neck is thinner and more delicate than the rest of the face. Specialized products are formulated with gentler ingredients and textures appropriate for these areas, helping to maintain hydration and a smooth, refreshed appearance.</p>
</details>
<details>
<summary><strong>Q: Can eye and neck treatments be added to existing facial services?</strong></summary>
<p>Absolutely. Eye and neck treatments are popular add-on services that enhance the overall facial experience. They allow estheticians to offer a more comprehensive treatment while increasing service revenue per client visit.</p>
</details>
<details>
<summary><strong>Q: Are these products available at wholesale pricing for professionals?</strong></summary>
<p>Yes, all eye and neck care products are available at wholesale pricing for licensed estheticians, spa owners, and clinic professionals across Canada. Contact us for volume discounts on your most-used products.</p>
</details>
</div>
</div>""",
        [
            ("Why do the eye and neck areas need specialized products?",
             "The skin around the eyes and neck is thinner and more delicate than the rest of the face. Specialized products are formulated with gentler ingredients and textures appropriate for these areas, helping to maintain hydration and a smooth, refreshed appearance."),
            ("Can eye and neck treatments be added to existing facial services?",
             "Absolutely. Eye and neck treatments are popular add-on services that enhance the overall facial experience. They allow estheticians to offer a more comprehensive treatment while increasing service revenue per client visit."),
            ("Are these products available at wholesale pricing for professionals?",
             "Yes, all eye and neck care products are available at wholesale pricing for licensed estheticians, spa owners, and clinic professionals across Canada. Contact us for volume discounts on your most-used products."),
        ]
    ),

    "best-sellers": (
        """<div class="collection-seo-content">
<h2>Best Sellers — Top Korean Dermaceutical Products Trusted by Canadian Estheticians</h2>
<p>Discover our <strong>best-selling Korean dermaceutical products</strong> — the most popular items ordered by estheticians, spa owners, and clinic professionals across Canada. This collection features the products that skincare professionals reorder most frequently, proven by real demand from the professional beauty community.</p>
<p>Our best sellers span every major skincare category including cleansers, serums, masks, treatments, and moisturizers from trusted brands like KRX Aesthetics and Corthe. These products have earned their best-seller status through consistent quality, reliable results, and positive feedback from the professionals who use them daily.</p>
<p>Not sure where to start? Our best sellers collection is the perfect introduction to Korean professional skincare. Each product has been validated by hundreds of Canadian estheticians. Available at <strong>wholesale pricing</strong> with fast shipping across Canada.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: How are best sellers determined at Beauty Connect Shop?</strong></summary>
<p>Our best sellers are determined by actual order volume from Canadian estheticians, spa owners, and clinic professionals. Products in this collection are the most frequently purchased and reordered items in our catalog.</p>
</details>
<details>
<summary><strong>Q: Is the best sellers collection a good starting point for new clinics?</strong></summary>
<p>Yes, our best sellers collection is an excellent starting point. These products have been validated by the professional community and represent the most popular Korean dermaceutical items that clinics rely on for their treatment menus.</p>
</details>
<details>
<summary><strong>Q: How often is the best sellers collection updated?</strong></summary>
<p>We regularly update our best sellers collection to reflect current ordering trends among Canadian skincare professionals. New products are added as they gain popularity, ensuring this collection always represents what is most in-demand.</p>
</details>
</div>
</div>""",
        [
            ("How are best sellers determined at Beauty Connect Shop?",
             "Our best sellers are determined by actual order volume from Canadian estheticians, spa owners, and clinic professionals. Products in this collection are the most frequently purchased and reordered items in our catalog."),
            ("Is the best sellers collection a good starting point for new clinics?",
             "Yes, our best sellers collection is an excellent starting point. These products have been validated by the professional community and represent the most popular Korean dermaceutical items that clinics rely on for their treatment menus."),
            ("How often is the best sellers collection updated?",
             "We regularly update our best sellers collection to reflect current ordering trends among Canadian skincare professionals. New products are added as they gain popularity, ensuring this collection always represents what is most in-demand."),
        ]
    ),

    "cosmetics": (
        """<div class="collection-seo-content">
<h2>Professional Korean Cosmetics — Wholesale Makeup Products for Spas</h2>
<p>Complete your client's experience with our <strong>professional Korean cosmetics</strong> collection. Beauty Connect Shop offers select Korean makeup and cosmetic products chosen specifically for use in spa, clinic, and salon settings across Canada.</p>
<p>Korean cosmetics are renowned worldwide for their innovative textures, skin-friendly formulations, and flawless finish. Our curated cosmetics selection includes products that complement professional skincare treatments, allowing estheticians to offer a polished finishing touch after facial services.</p>
<p>Offering cosmetics alongside skincare treatments creates additional revenue opportunities for your practice. Stock these <strong>professional-grade Korean cosmetics</strong> at wholesale prices from Beauty Connect Shop.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What types of Korean cosmetics does Beauty Connect Shop carry?</strong></summary>
<p>We carry a curated selection of professional Korean cosmetic products suitable for use in spa and clinic settings. Our focus is on products that complement professional skincare treatments and deliver a natural, polished finish.</p>
</details>
<details>
<summary><strong>Q: Can estheticians add cosmetics to their treatment offerings?</strong></summary>
<p>Yes, many estheticians offer a cosmetics finishing step after facial treatments as an add-on service. This enhances the client experience and provides an additional revenue stream for your practice.</p>
</details>
<details>
<summary><strong>Q: Are Korean cosmetics suitable for sensitive skin after facial treatments?</strong></summary>
<p>Korean cosmetic formulations are generally known for their gentle, skin-friendly ingredients. Our curated selection prioritizes products appropriate for use after professional skincare treatments, but estheticians should always assess individual client sensitivity.</p>
</details>
</div>
</div>""",
        [
            ("What types of Korean cosmetics does Beauty Connect Shop carry?",
             "We carry a curated selection of professional Korean cosmetic products suitable for use in spa and clinic settings. Our focus is on products that complement professional skincare treatments and deliver a natural, polished finish."),
            ("Can estheticians add cosmetics to their treatment offerings?",
             "Yes, many estheticians offer a cosmetics finishing step after facial treatments as an add-on service. This enhances the client experience and provides an additional revenue stream for your practice."),
            ("Are Korean cosmetics suitable for sensitive skin after facial treatments?",
             "Korean cosmetic formulations are generally known for their gentle, skin-friendly ingredients. Our curated selection prioritizes products appropriate for use after professional skincare treatments, but estheticians should always assess individual client sensitivity."),
        ]
    ),

    "body-care": (
        """<div class="collection-seo-content">
<h2>Professional Korean Body Care — Wholesale Body Skincare for Clinics</h2>
<p>Extend the Korean skincare experience beyond the face with our <strong>professional body care</strong> collection. Beauty Connect Shop offers select Korean body care products formulated for use in spa, clinic, and wellness settings across Canada.</p>
<p>Our body care range includes professional body creams, hydrating lotions, exfoliating treatments, and specialty body care products. Each formulation brings the same advanced Korean skincare innovation found in our facial products to body treatments, helping clients maintain smooth, hydrated, and healthy-looking skin from head to toe.</p>
<p>Body care treatments are growing in popularity as clients seek comprehensive wellness experiences. Add body care services to your treatment menu with these <strong>professional-grade products</strong> at wholesale prices.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What body care products does Beauty Connect Shop offer for professionals?</strong></summary>
<p>We offer professional body creams, hydrating lotions, exfoliating body treatments, and specialty body care products. All products are formulated for use in professional spa and clinic settings and are available at wholesale pricing.</p>
</details>
<details>
<summary><strong>Q: Can body care treatments increase clinic revenue?</strong></summary>
<p>Absolutely. Body care add-ons and standalone body treatments are increasingly popular among spa clients. Offering professional Korean body care services can diversify your menu and increase average revenue per client visit.</p>
</details>
<details>
<summary><strong>Q: Are Korean body care products different from regular body lotions?</strong></summary>
<p>Professional Korean body care products feature more advanced formulations with higher-quality ingredients compared to standard retail products. They are designed for professional application and deliver more intensive hydration and skin appearance benefits.</p>
</details>
</div>
</div>""",
        [
            ("What body care products does Beauty Connect Shop offer for professionals?",
             "We offer professional body creams, hydrating lotions, exfoliating body treatments, and specialty body care products. All products are formulated for use in professional spa and clinic settings and are available at wholesale pricing."),
            ("Can body care treatments increase clinic revenue?",
             "Absolutely. Body care add-ons and standalone body treatments are increasingly popular among spa clients. Offering professional Korean body care services can diversify your menu and increase average revenue per client visit."),
            ("Are Korean body care products different from regular body lotions?",
             "Professional Korean body care products feature more advanced formulations with higher-quality ingredients compared to standard retail products. They are designed for professional application and deliver more intensive hydration and skin appearance benefits."),
        ]
    ),

    "new-products": (
        """<div class="collection-seo-content">
<h2>New Products — Latest Korean Dermaceutical Arrivals for Professionals</h2>
<p>Stay ahead of the curve with the <strong>latest Korean dermaceutical products</strong> at Beauty Connect Shop. Our new arrivals collection showcases the most recent additions to our professional catalog, bringing cutting-edge Korean skincare innovation to estheticians and clinic professionals across Canada.</p>
<p>We continuously source the newest professional-grade products from Korea's leading dermaceutical brands. From innovative serum formulations and next-generation treatment masks to advanced skincare devices and breakthrough ingredient technologies, our new products collection is your first look at what is trending in professional Korean skincare.</p>
<p>Be among the first Canadian estheticians to offer the latest Korean skincare innovations in your practice. All new products are available at <strong>wholesale pricing</strong> with fast shipping across Canada.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: How often does Beauty Connect Shop add new products?</strong></summary>
<p>We regularly add new Korean dermaceutical products to our catalog. Check this collection frequently or subscribe to our newsletter to be notified when new professional skincare products arrive from Korea.</p>
</details>
<details>
<summary><strong>Q: Are new products available at the same wholesale pricing?</strong></summary>
<p>Yes, all new arrivals are available at our standard wholesale pricing for licensed estheticians and clinic professionals. Introductory offers may be available on select new products — contact our team for details.</p>
</details>
<details>
<summary><strong>Q: Can I request specific Korean skincare products to be added?</strong></summary>
<p>Absolutely. We welcome product suggestions from our professional clients. If there is a specific Korean dermaceutical product or brand you would like to see in our catalog, contact our sourcing team and we will do our best to make it available.</p>
</details>
</div>
</div>""",
        [
            ("How often does Beauty Connect Shop add new products?",
             "We regularly add new Korean dermaceutical products to our catalog. Check this collection frequently or subscribe to our newsletter to be notified when new professional skincare products arrive from Korea."),
            ("Are new products available at the same wholesale pricing?",
             "Yes, all new arrivals are available at our standard wholesale pricing for licensed estheticians and clinic professionals. Introductory offers may be available on select new products — contact our team for details."),
            ("Can I request specific Korean skincare products to be added?",
             "Absolutely. We welcome product suggestions from our professional clients. If there is a specific Korean dermaceutical product or brand you would like to see in our catalog, contact our sourcing team and we will do our best to make it available."),
        ]
    ),

    "frontpage": (
        """<div class="collection-seo-content">
<h2>Beauty Connect Shop — Canada's Trusted Korean Dermaceutical Distributor</h2>
<p>Welcome to <strong>Beauty Connect Shop</strong>, Canada's premier B2B distributor of professional Korean dermaceutical products. We serve licensed estheticians, spa owners, dermatology clinics, and skincare professionals with the finest Korean skincare brands at wholesale prices.</p>
<p>Our curated catalog features over 200 professional-grade products from leading Korean brands including KRX Aesthetics, Corthe, and Zena Cosmetics. From advanced serums and professional peels to treatment masks and complete facial protocols, we provide everything your practice needs to deliver exceptional Korean skincare experiences.</p>
<p>Beauty Connect Shop is more than a supplier — we are your partner in building a successful professional skincare practice. Enjoy competitive wholesale pricing, fast nationwide Canadian shipping, dedicated B2B support, and access to professional training resources. Join hundreds of Canadian estheticians who trust us as their go-to Korean skincare source.</p>

<h3>Frequently Asked Questions</h3>
<div class="faq-section">
<details>
<summary><strong>Q: What is Beauty Connect Shop?</strong></summary>
<p>Beauty Connect Shop is a B2B Korean dermaceutical distributor based in Canada. We provide professional-grade Korean skincare products at wholesale prices exclusively for licensed estheticians, spa owners, and clinic professionals.</p>
</details>
<details>
<summary><strong>Q: Who can shop at Beauty Connect Shop?</strong></summary>
<p>Our products are available to licensed estheticians, spa owners, dermatology clinics, and skincare professionals across Canada. We offer wholesale pricing and B2B account options for qualified businesses.</p>
</details>
<details>
<summary><strong>Q: Does Beauty Connect Shop ship across Canada?</strong></summary>
<p>Yes, we offer fast, reliable nationwide shipping across all Canadian provinces and territories. Most orders are processed within 1-2 business days with tracking provided on every shipment.</p>
</details>
</div>
</div>""",
        [
            ("What is Beauty Connect Shop?",
             "Beauty Connect Shop is a B2B Korean dermaceutical distributor based in Canada. We provide professional-grade Korean skincare products at wholesale prices exclusively for licensed estheticians, spa owners, and clinic professionals."),
            ("Who can shop at Beauty Connect Shop?",
             "Our products are available to licensed estheticians, spa owners, dermatology clinics, and skincare professionals across Canada. We offer wholesale pricing and B2B account options for qualified businesses."),
            ("Does Beauty Connect Shop ship across Canada?",
             "Yes, we offer fast, reliable nationwide shipping across all Canadian provinces and territories. Most orders are processed within 1-2 business days with tracking provided on every shipment."),
        ]
    ),
}


# SEO Meta for each collection (title max 60 chars, description max 155 chars)
COLLECTION_SEO = {
    "krx": ("KRX Aesthetics Professional Korean Skincare Canada", "Shop KRX Aesthetics dermaceutical products for estheticians. Authorized Canadian distributor. Wholesale pricing, fast shipping. Trusted by professionals."),
    "zena-cosmetics": ("Zena Cosmetics Korean Skincare for Professionals", "Shop Zena Cosmetics professional Korean skincare at wholesale prices. Premium formulations for estheticians and clinics in Canada. Fast shipping."),
    "corthe": ("Corthe Korean Dermaceuticals for Clinics Canada", "Shop Corthe professional Korean skincare for clinics and spas. Advanced formulations for estheticians. Wholesale pricing in Canada. Shop now."),
    "bundle-kits": ("Professional Skincare Bundle Kits | K-Beauty Canada", "Save with curated Korean skincare bundle kits for estheticians. Professional-grade products at wholesale prices. Fast Canadian shipping. Shop now."),
    "teeth-whitening-supplies": ("Professional Teeth Whitening Supplies Canada", "Shop professional teeth whitening supplies for clinics and spas. Premium Korean whitening systems at wholesale pricing. Fast Canadian shipping."),
    "lash-supplies": ("Professional Lash Extension Supplies Canada", "Shop premium lash extension supplies for professionals. Korean lash products at wholesale pricing for salons and clinics. Fast Canadian shipping."),
    "all-products": ("All Professional Korean Skincare Products Canada", "Browse 200+ professional Korean skincare products. K-beauty for estheticians at wholesale prices. KRX, Corthe, Zena Cosmetics. Shop now."),
    "cleansers": ("Professional Korean Cleansers for Estheticians", "Shop professional-grade Korean cleansers for spas and clinics. Deep cleansing, gentle formulations. Wholesale pricing in Canada. Shop now."),
    "masks": ("Professional Korean Face Masks for Clinics Canada", "Shop 40+ professional Korean face masks for estheticians. Treatment masks, modeling masks, sheet masks at wholesale. Fast Canadian shipping."),
    "peels": ("Professional Korean Chemical Peels for Clinics", "Shop professional Korean peels for estheticians and clinics. Gentle exfoliation, skin resurfacing. Wholesale pricing in Canada. Shop now."),
    "serums-ampoules": ("Professional Korean Serums & Ampoules Canada", "Shop professional Korean serums and ampoules for estheticians. PDRN, peptides, niacinamide formulations. Wholesale pricing. Fast shipping."),
    "toners-essences": ("Professional Korean Toners & Essences Canada", "Shop professional Korean toners and essences for estheticians. Hydrating, pH-balancing formulations. Wholesale pricing. Fast Canadian shipping."),
    "treatments": ("Professional Korean Skin Treatments Canada", "Shop professional Korean skin treatment products for clinics. Advanced formulations for estheticians. Wholesale pricing in Canada. Shop now."),
    "moisturizers": ("Professional Korean Moisturizers for Clinics", "Shop professional Korean moisturizers for estheticians. Deep hydration, barrier support formulations. Wholesale pricing. Fast Canadian shipping."),
    "hydrofacial-solutions": ("HydroFacial Solutions for Professional Clinics", "Shop professional HydroFacial solutions and serums. Korean formulations for clinics and spas. Wholesale pricing in Canada. Fast shipping."),
    "eye-neck-care": ("Professional Korean Eye & Neck Care Canada", "Shop professional Korean eye and neck care products. Firming, hydrating formulations for estheticians. Wholesale pricing. Fast Canadian shipping."),
    "best-sellers": ("Best Selling Korean Skincare for Professionals", "Shop our best-selling professional Korean skincare products. Top-rated by Canadian estheticians. Wholesale pricing, fast shipping. Shop now."),
    "cosmetics": ("Professional Korean Cosmetics for Clinics Canada", "Shop professional Korean cosmetics for spas and clinics. Premium formulations at wholesale pricing for estheticians in Canada. Fast shipping."),
    "body-care": ("Professional Korean Body Care Products Canada", "Shop professional Korean body care for estheticians. Body treatments, scrubs, moisturizers at wholesale. Fast Canadian shipping. Shop now."),
    "new-products": ("New Korean Skincare Products for Professionals", "Discover the latest professional Korean skincare arrivals. New products for estheticians at wholesale pricing. Fast Canadian shipping. Shop now."),
    "trainings": ("Professional Skincare Training Programs Canada", "Enroll in professional skincare training programs. Korean skincare certification for estheticians. Learn advanced techniques. Register now."),
}


def build_faq_jsonld(faqs):
    """Build FAQ JSON-LD structured data."""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a
                }
            }
            for q, a in faqs
        ]
    })


def main():
    print("=" * 70)
    print("  Beauty Connect Shop — Collection Description & FAQ Pusher")
    print("=" * 70)

    # 1. Fetch all collections
    print("\nFetching collections from Shopify...")
    query = """
    {
        collections(first: 50) {
            nodes {
                id
                title
                handle
                descriptionHtml
                productsCount { count }
            }
        }
    }
    """
    data = graphql(query)
    collections = data.get('data', {}).get('collections', {}).get('nodes', [])
    print(f"Found {len(collections)} collections\n")

    # 2. Identify collections that need updating (all except frontpage/homepage)
    to_update = []
    skipped = []

    for c in collections:
        handle = c['handle']
        if handle == 'frontpage':
            skipped.append(c)
            print(f"  SKIP (homepage): {c['title']}")
        elif handle in COLLECTION_CONTENT:
            to_update.append(c)
        else:
            skipped.append(c)
            print(f"  SKIP (no content defined): {c['title']} ({handle})")

    print(f"\nCollections to update: {len(to_update)}")
    print(f"Collections skipped:   {len(skipped)}\n")

    # 3. Push updates
    success = 0
    failed = 0

    for c in to_update:
        handle = c['handle']
        cid = c['id']
        title = c['title']

        if handle not in COLLECTION_CONTENT:
            print(f"  SKIP (no content defined): {title}")
            continue

        html_content, faqs = COLLECTION_CONTENT[handle]
        faq_jsonld = build_faq_jsonld(faqs)

        print(f"  Updating: {title} ({handle})")
        print(f"    HTML: {len(html_content)} chars")
        print(f"    FAQs: {len(faqs)} questions")

        # Get SEO meta for this collection
        seo_meta = COLLECTION_SEO.get(handle, (None, None))
        seo_title = seo_meta[0]
        seo_desc = seo_meta[1]

        if seo_title:
            print(f"    SEO Title: {seo_title} ({len(seo_title)} chars)")
        if seo_desc:
            print(f"    SEO Desc:  {seo_desc[:80]}... ({len(seo_desc)} chars)")

        # Update descriptionHtml + SEO
        ok1 = update_collection(cid, html_content, seo_title=seo_title, seo_description=seo_desc)
        if ok1:
            print(f"    descriptionHtml: OK")
        else:
            print(f"    descriptionHtml: FAILED")

        # Set FAQ JSON-LD metafield
        ok2 = set_faq_metafield(cid, faq_jsonld)
        if ok2:
            print(f"    FAQ metafield:   OK")
        else:
            print(f"    FAQ metafield:   FAILED")

        if ok1 and ok2:
            success += 1
        else:
            failed += 1

        time.sleep(0.5)  # Rate limiting
        print()

    # 4. Summary
    print("=" * 70)
    print(f"  COMPLETE")
    print(f"  Updated:  {success}")
    print(f"  Failed:   {failed}")
    print(f"  Skipped:  {len(skipped)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
