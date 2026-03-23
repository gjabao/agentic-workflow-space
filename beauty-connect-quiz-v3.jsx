import { useState } from "react";

const B = { dark: "#2C1810", gold: "#DFBA90", cream: "#FAF8F5", gray: "#8B7D6B", lgold: "#F0E0CC" };

// Klaviyo public key (site ID) - safe for client-side use
const KLAVIYO_PUBLIC_KEY = window.__KLAVIYO_PUBLIC_KEY || "";

// ─── KLAVIYO INTEGRATION ────────────────────────────────────
const sendToKlaviyo = async (email, name, biz, answers, products) => {
  if (!KLAVIYO_PUBLIC_KEY) return;
  const concern = answers.concern === "aging" ? "Anti-Aging" : answers.concern === "acne" ? "Acne Management" : answers.concern === "pigment" ? "Brightening" : "Sensitivity";
  try {
    // Identify profile
    await fetch("https://a.klaviyo.com/client/profiles/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "revision": "2024-10-15" },
      body: JSON.stringify({
        data: {
          type: "profile",
          attributes: {
            email,
            first_name: name,
            properties: {
              business_name: biz,
              quiz_concern: answers.concern,
              quiz_sub_concern: answers.sub,
              quiz_skin_type: answers.skin,
              quiz_experience: answers.exp,
              quiz_client_age: answers.clientAge,
              quiz_goal: answers.goal,
              quiz_modality: answers.modality,
              quiz_budget: answers.budget,
              quiz_completed_at: new Date().toISOString(),
            },
          },
        },
        company_id: KLAVIYO_PUBLIC_KEY,
      }),
    });
    // Track event
    await fetch("https://a.klaviyo.com/client/events/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "revision": "2024-10-15" },
      body: JSON.stringify({
        data: {
          type: "event",
          attributes: {
            metric: { data: { type: "metric", attributes: { name: "Quiz Completed" } } },
            profile: { data: { type: "profile", attributes: { email } } },
            properties: {
              concern,
              sub_concern: answers.sub,
              protocol_name: `${concern} Protocol`,
              product_count: products.length,
              products: products.map(p => ({ name: p.n, tag: p.tag, price: p.p, url: p.u, image: p.img, why: p.why })),
            },
          },
        },
        company_id: KLAVIYO_PUBLIC_KEY,
      }),
    });
  } catch (e) {
    console.warn("Klaviyo tracking skipped:", e.message);
  }
};

// ─── VERIFIED PRODUCT CATALOG (from Google Sheet) ───────────
const P = {
  // CLEANSERS
  enzymeCleanser: { n: "KrX - Enzyme Milk Cleanser", p: "$46.00", u: "https://beautyconnectshop.com/products/krx-enzyme-milk-cleanser-250ml", img: "https://beautyconnectshop.com/cdn/shop/files/KRX-Gentle-Enzyme-Milk-Cleanser.webp?v=1737147738", d: "Gentle antibac formula. Perfect pre-treatment step for all protocols." },
  gelCleanser: { n: "KrX - Gel Cleanser", p: "$32.00", u: "https://beautyconnectshop.com/products/krx-gel-cleanser", img: "https://beautyconnectshop.com/cdn/shop/files/krx-gel-cleanser-618872_1100x_fc4e96f7-0888-4fc2-90b2-3c7cc639a9ba.jpg", d: "Lightweight gel for oily/combo skin. Great for acne-prone clients." },
  probioticWash: { n: "KrX - Probiotic Face Wash", p: "$37.00", u: "https://beautyconnectshop.com/products/krx-probiotic-face-wash", img: "https://beautyconnectshop.com/cdn/shop/files/prausiklis-su-probiotikais-probiotic-face-wash-krx-100-ml.jpg?v=1737149283", d: "Tri-probiotic complex rebuilds microbiome. Ideal for compromised barriers." },
  preCleansingOil: { n: "KrX - Pre Cleansing Oil", p: "$37.00", u: "https://beautyconnectshop.com/products/krx-pre-cleansing-oil-with-fermented-extracts", img: "https://beautyconnectshop.com/cdn/shop/files/IMG_3436.jpg?v=1737148290", d: "Fermented extracts dissolve makeup + SPF without stripping." },
  cocoaWash: { n: "KRX - Cocoa Facial Powder Wash", p: "$37.00", u: "https://beautyconnectshop.com/products/krx-cocoa-facial-powder-wash", img: "https://beautyconnectshop.com/cdn/shop/files/krx-cocoa-facial-powder-wash-526923.webp?v=1737147532", d: "Antioxidant-rich cocoa powder exfoliates gently for radiance." },
  oxyPumpkin: { n: "KrX - OxyGlow Pumpkin Bubble Cleanser", p: "$37.70", u: "https://beautyconnectshop.com/products/krx-oxyglow-pumpkin-bubble-cleanser", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign_6_2e6ddd1a-30e4-4d7c-9916-ab9c6cbda4fc.webp?v=1737148108", d: "Fun bubble texture clients love. Pumpkin enzymes dissolve dead cells." },
  cortheCleansingOil: { n: "Corthe – Essential Cleansing Oil", p: "$32.80", u: "https://beautyconnectshop.com/products/corthe-dermo-essential-cleansing-oil-150ml", img: "https://beautyconnectshop.com/cdn/shop/files/corthe-dermo-essential-cleansing-oil-281088.webp?v=1737150906", d: "Dissolves impurities while maintaining moisture balance." },
  cortheCleansingMilk: { n: "Corthe – Cleansing Milk", p: "$38.44", u: "https://beautyconnectshop.com/products/corthe-dermo-cleansing-milk", img: "https://beautyconnectshop.com/cdn/shop/files/cleansing-milk.webp?v=1737150871", d: "pH-balanced milk cleanser for sensitive/reactive skin." },
  youthplexCleanser: { n: "KRX - Youthplex Cleansing Fluid", p: "$77.00", u: "https://beautyconnectshop.com/products/krx-youthplex-cleansing-fluid", img: "https://beautyconnectshop.com/cdn/shop/files/YouthPlex_Wash.png?v=1749583970", d: "Anti-aging cleanser with peptides. Preps mature skin." },
  // PEELS & RESURFACING
  r3Peel: { n: "KRX - R-3 Therapeel", p: "$154.96", u: "https://beautyconnectshop.com/products/krx-r-3-therapeel-krx-chemical-peel-certification-required", img: "https://beautyconnectshop.com/cdn/shop/files/file.jpg?v=1737145250", d: "Retinol-based resurfacing. Fades dark spots + accelerates cell turnover." },
  lzPeel: { n: "KRX - LZ Peel", p: "$154.96", u: "https://beautyconnectshop.com/products/krx-lazer-peel-krx-chemical-peel-certification-required", img: "https://beautyconnectshop.com/cdn/shop/files/captureaa-900x900.webp?v=1737147990", d: "Advanced resurfacing for mature/sun-damaged skin." },
  greenSea: { n: "KrX Green Sea Peel", p: "$154.49", u: "https://beautyconnectshop.com/products/krx-green-sea-peel", img: "https://beautyconnectshop.com/cdn/shop/files/krx-green-sea-peel-881608.webp?v=1737148735", d: "Herbal peel for texture/scarring. 3-5 day downtime." },
  bioherb: { n: "KrX - Bioherb 50 Herbal", p: "$33.28", u: "https://beautyconnectshop.com/products/krx-bioherb-50-herbal-resurfacing-peel", img: "https://beautyconnectshop.com/cdn/shop/files/krx-bioherb-50-herbal-resurfacing-peel-346036_1100x_0fd5089d-44aa-4e94-b26a-a69f50a4a5c4.jpg?v=1737147138", d: "50-herb blend. Gentle enough for regular use, nourishes while resurfacing." },
  biphase: { n: "Biphase Regepeel", p: "$154.96", u: "https://beautyconnectshop.com/products/biphase-regepeel-15-ml", img: "https://beautyconnectshop.com/cdn/shop/files/bifase-peel-zena-2.webp?v=1733514909", d: "Dual-phase peel: exfoliation + nourishment in one step." },
  cortheOxyPeel: { n: "Corthe - Bright OXY PEEL", p: "$84.00", u: "https://beautyconnectshop.com/products/corthe-dermo-bright-lightening-oxy-peel-100-ml", img: "https://beautyconnectshop.com/cdn/shop/files/CORTHE_Dermo_Bright_LIGHTENING_OXY_PEEL_2.jpg?v=1733610420", d: "Brightening peel for pigmentation. No downtime." },
  mtsPrep: { n: "KrX - MTS Prep Kit", p: "$109.00", u: "https://beautyconnectshop.com/products/krx-mts-prep-kit-exfoliant-gel-neutralizing-foam", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1055.jpg?v=1737148960", d: "Exfoliant gel + neutralizer. Essential prep for microneedling." },
  // LIFTING & ANTI-AGING
  threadfill: { n: "KrX Thread-Fill Ampoule", p: "$149.00", u: "https://beautyconnectshop.com/products/krx-thread-fill-ampoule", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-3691.webp?v=1749318817", d: "Absorbable collagen threads for needle-less threadlift therapy." },
  haFilling: { n: "KRX - Premium HA Filling Powder (5)", p: "$134.16", u: "https://beautyconnectshop.com/products/krx-premium-ha-filling-powder-5-ampoules", img: "https://beautyconnectshop.com/cdn/shop/files/Hafillingpowder.jpg?v=1749584449", d: "3 molecular weights of nano HA. Fills volume loss in temples, under-eyes, smile lines." },
  undereyeSol: { n: "KrX - Premium Undereye Solution (5)", p: "$134.16", u: "https://beautyconnectshop.com/products/krx-premium-undereye-solution-5pcs", img: "https://beautyconnectshop.com/cdn/shop/files/krx-premium-undereye-solution-812662_1100x_03432293-acff-4158-94e5-9bdd8878", d: "Meso-grade formula targeting dark circles, hollowing & fine lines." },
  vtoxMask: { n: "KRX - V-Tox Higher Power Lift Mask", p: "$145.60", u: "https://beautyconnectshop.com/products/krx-v-tox-higher-power-lift-mask-100ml", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1200.jpg?v=1733533440", d: "Peel-off contouring mask for jawline & V-line definition." },
  faceLiftSerum: { n: "KrX - Face Lift Intensive Firming Serum", p: "$37.70", u: "https://beautyconnectshop.com/products/krx-the-face-lift-intensive-firming-serum", img: "https://beautyconnectshop.com/cdn/shop/files/face-lift-serum.webp?v=1737151384", d: "Budget-friendly lifting serum for daily firming support." },
  youthplexSerum: { n: "KrX - Youthplex Face Lift Serum", p: "$69.00", u: "https://beautyconnectshop.com/products/krx-youthplex-face-lift-serum", img: "https://beautyconnectshop.com/cdn/shop/files/YouthPlex_Serum.png?v=1749583876", d: "Smooths fine lines, boosts bounce. For normal, dry, combo & mature skin." },
  youthplexCream: { n: "KrX - Youthplex Face Lift Cream", p: "$63.00", u: "https://beautyconnectshop.com/products/krx-youthplex-face-lift-cream", img: "https://beautyconnectshop.com/cdn/shop/files/KrX_Youthplex_Face_Lift_Cream.jpg?v=1737151740", d: "Firms, sculpts, reduces fine lines. AM/PM finishing step." },
  // BRIGHTENING & PIGMENTATION
  melaSerum: { n: "KrX Mela Défense Brightening Serum", p: "$45.50", u: "https://beautyconnectshop.com/products/krx-mela-defense-whitening-serum", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign_11.webp?v=1737148827", d: "Tranexamic Acid + Niacinamide. Inhibits melanin production, fades dark spots." },
  melaCream: { n: "KrX - Mela Défense Brightening Cream", p: "$49.50", u: "https://beautyconnectshop.com/products/krx-mela-defense-whitening-cream", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign_12.webp?v=1737148851", d: "Daily brightening cream for maintenance between treatments." },
  glowSerum: { n: "KrX - All Day Glow Vitamin Serum", p: "$36.00", u: "https://beautyconnectshop.com/products/krx-ha-vita-c-serum-30ml", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign_92_cf6706ec-85c9-4219-9af5-1e0e36063cbc.jpg?v=1733529277", d: "Vitamin C serum for cumulative brightening and antioxidant protection." },
  glowToner: { n: "KrX - All Day Glow Quenching Toner", p: "$36.40", u: "https://beautyconnectshop.com/products/krx-all-day-glow-quenching-toner-120ml", img: "https://beautyconnectshop.com/cdn/shop/files/krx-quenching-glow-toner-993993.webp?v=1749918040", d: "Prep toner that primes skin for brightening actives." },
  zenaBrightening: { n: "Zena - Pro Brightening Serum", p: "from $39.99", u: "https://beautyconnectshop.com/products/zena-cosmetics-pro-brightening-plus", img: "https://beautyconnectshop.com/cdn/shop/files/0E5D5C61-9720-4AB3-9B68-A69D5D14567B.jpg?v=1748582019", d: "Professional-grade brightening. Targets dark spots for uniform tone." },
  cortheIonTo: { n: "CORTHE - Bright ION-TO Ampoule", p: "$107.39", u: "https://beautyconnectshop.com/products/corthe-dermo-bright-ion-to-ampoule", img: "https://beautyconnectshop.com/cdn/shop/files/CORTHE_Dermo_Bright_ION-TO_AMPOULE_2.jpg?v=1733610293", d: "Botanic placenta. Works with iontophoresis for clinical-grade brightening." },
  cortheSpot: { n: "Corthe – Bright Spot Lumedic", p: "$63.54", u: "https://beautyconnectshop.com/products/corthe-dermo-bright-spot-lumedic-150-ml", img: "https://beautyconnectshop.com/cdn/shop/files/sunspot.webp?v=1737142577", d: "Targeted dark spot corrector for stubborn pigmentation." },
  cortheBrightC: { n: "Corthe – Bright C Ampoule", p: "$33.49", u: "https://beautyconnectshop.com/products/corthe-dermo-bright-c-ampoule-50-ml", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign-2024-01-04T162751.146.webp?v=1737167841", d: "Vitamin C concentrate for glow-boosting and antioxidant defence." },
  cortheBrightCream: { n: "Corthe – Bright Brightening Cream", p: "$43.20", u: "https://beautyconnectshop.com/products/corthe-bright-brightening-cream-50gm", img: "https://beautyconnectshop.com/cdn/shop/files/corthe-dermo-bright-brightening-cream-247014.webp?v=1733606616", d: "Daily brightening moisturizer for even complexion." },
  // ACNE & CLEARING
  pd13: { n: "KrX PD-13 Therapy", p: "$149.00", u: "https://beautyconnectshop.com/products/krx-pd-13-acne-therapy", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign-2022-06-12T170246.572.jpg?v=1733531387", d: "Advanced peptide delivery for deep acne repair and regeneration." },
  inflacure: { n: "KRX Inflacure Healing Active", p: "$69.00", u: "https://beautyconnectshop.com/products/krx-inflacure-healing-active", img: "https://beautyconnectshop.com/cdn/shop/files/krxinflacurehealingactive.png?v=1742082109", d: "Anti-inflammatory concentrate. Apply directly on extracted areas." },
  preExtraction: { n: "KrX - Pre Extraction Softening Mask", p: "$46.00", u: "https://beautyconnectshop.com/products/krx-pre-extraction-softening-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG_3435.jpg?v=1733531685", d: "Softens comedones for easier, less traumatic extractions." },
  pureSpot: { n: "Corthe – Pure Spot For Night", p: "$32.29", u: "https://beautyconnectshop.com/products/corthe-dermo-pure-spot-for-night-20-ml", img: "https://beautyconnectshop.com/cdn/shop/files/corthe-dermo-pure-spot-for-night-614327.webp?v=1733609024", d: "Overnight blemish assassin. Shrinks spots while clients sleep." },
  // HYDRATION & BARRIER REPAIR
  carboxySmall: { n: "KRX Carboxy Therapy (6 tx)", p: "$102.96", u: "https://beautyconnectshop.com/products/krx-carboxy-therapy-mini", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1145.jpg?v=1733523646", d: "CO₂ infusion stimulates circulation. Pairs with threadfill for lifting." },
  carboxyLarge: { n: "KrX - CO2 Carboxy Therapy (20 tx)", p: "$206.96", u: "https://beautyconnectshop.com/products/krx-co2-carboxy-therapy-20-treatments", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1145_da70dd0f-09b5-4cea-8d69-1b7f8a0ae1cc.jpg?v=1733525147", d: "Bulk value. 20 treatments — essential for high-volume clinics." },
  jellyMist: { n: "KRX - Jelly Mist", p: "$43.00", u: "https://beautyconnectshop.com/products/krx-jelly-mist", img: "https://beautyconnectshop.com/cdn/shop/files/my-11134207-7rasc-m1nuzu0i2wi2e3.jpg?v=1742082541", d: "Spray-on gel mask: 20x more absorption than sheet masks, 6hr nutrient delivery." },
  essencePads: { n: "KRX - Essence Cream Pads", p: "$60.84", u: "https://beautyconnectshop.com/products/krx-essence-cream-pads", img: "https://beautyconnectshop.com/cdn/shop/files/WhatsApp-Image-2024-08-03-at-08.52.43-3.jpg?v=1733526847", d: "Pre-soaked pads for quick hydration between treatment steps." },
  eyeDarts: { n: "KrX - Undereye Darts", p: "$19.75", u: "https://beautyconnectshop.com/products/krx-undereye-darts", img: "https://beautyconnectshop.com/cdn/shop/files/WhatsApp-Image-2024-05-29-at-12.51.52.jpg?v=1737148529", d: "Dissolving microneedle patches for under-eye. Retail hit." },
  cryoCaps: { n: "KrX - Cryofacial Caps", p: "$46.00", u: "https://beautyconnectshop.com/products/krx-cryofacial-caps", img: "https://beautyconnectshop.com/cdn/shop/files/krx-cryofacial-caps-400995.webp?v=1737147860", d: "Cryotherapy effect tightens pores, reduces puffiness instantly." },
  zenaHyalnano: { n: "Zena - Hyalnano Serum", p: "$39.99", u: "https://beautyconnectshop.com/products/zena-hyalnano-serum", img: "https://beautyconnectshop.com/cdn/shop/files/WhatsApp_Image_2022-06-15_at_10.43.29_1_-300x300h.jpg?v=1737152026", d: "Nano hyaluronic acid penetrates deeper than standard HA." },
  cortheRelief: { n: "Corthe - RELIEF AMPOULE", p: "$45.21", u: "https://beautyconnectshop.com/products/corthe-relief-ampoule-100-ml", img: "https://beautyconnectshop.com/cdn/shop/files/Dermo-Sensitive-RELIEF-AMPOULE.jpg?v=1733613311", d: "Calms redness and reactive skin on contact." },
  cortheCica: { n: "Corthe – Sensitive Cica Ampoules", p: "$33.59", u: "https://beautyconnectshop.com/products/corthe-dermo-sensitive-cica-ampoules-50-ml", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign-2024-01-04T162659.788.webp?v=1737150980", d: "Centella asiatica concentrate for barrier restoration." },
  cortheBifida: { n: "Corthe – Bifida Ampoule", p: "$33.49", u: "https://beautyconnectshop.com/products/corthe-bifida-ampoule-50-ml", img: "https://beautyconnectshop.com/cdn/shop/files/AMPOI.webp?v=1737142540", d: "Bifida ferment lysate strengthens barrier + deep hydration." },
  // MOISTURIZERS & RECOVERY
  cicaCream: { n: "KrX - Cica Recovery Cream 25g", p: "$34.90", u: "https://beautyconnectshop.com/products/krx-cica-recovery-cream-25g", img: "https://beautyconnectshop.com/cdn/shop/files/Cicacream.jpg?v=1749585840", d: "Ceramide + centella for rapid barrier restoration post-treatment." },
  cicaAllDay: { n: "KrX - Cica All Day Cream 100g", p: "$56.00", u: "https://beautyconnectshop.com/products/krx-cica-recovery-all-day-cream", img: "https://beautyconnectshop.com/cdn/shop/files/7956AFAB-059B-4994-A611-DEA21C0120B3.jpg?v=1737147486", d: "Daily moisturizer with cica. Rebuilds barrier over time." },
  probioticCream: { n: "KrX - Probiotic Face Cream", p: "$41.00", u: "https://beautyconnectshop.com/products/krx-probiotic-face-cream", img: "https://beautyconnectshop.com/cdn/shop/files/Untitled_design_13.webp?v=1737149082", d: "Microbiome-supporting cream restores healthy skin flora." },
  aftercareCream: { n: "KrX - Aftercare Cream (100pcs box)", p: "$65.00", u: "https://beautyconnectshop.com/products/krx-repair-cream-100pcs", img: "https://beautyconnectshop.com/cdn/shop/files/IMG_6269_1.jpg?v=1737572574", d: "Individual sachets. Send home with every client post-treatment." },
  eyeCream: { n: "KrX - Active 31 Revitalizing Eye Cream", p: "$41.00", u: "https://beautyconnectshop.com/products/krx-active-31-revitalizing-eye-cream", img: "https://beautyconnectshop.com/cdn/shop/files/unnamed.jpg?v=1737143668", d: "31 active ingredients targeting crow's feet, puffiness, dark circles." },
  cortheMoisture: { n: "Corthe - Moisture Rx Recharging Cream", p: "$32.78", u: "https://beautyconnectshop.com/products/corthe-moisture-rx-recharging-cream-150-ml", img: "https://beautyconnectshop.com/cdn/shop/files/D2958AA2-D2E8-408C-88B8-E21BBBFCFEB6.png?v=1743118258", d: "Long-lasting hydration without greasy residue. All skin types." },
  cortheRichM: { n: "Corthe – Essential Rich M Cream", p: "from $32.13", u: "https://beautyconnectshop.com/products/corthe-dermo-essential-rich-m-cream", img: "https://beautyconnectshop.com/cdn/shop/files/corthe-dermo-essential-rich-m-cream-976775-1.webp?v=1737150951", d: "Rich nourishing cream. Ideal for dry/dehydrated skin." },
  revivalBalm: { n: "Corthe - Revival Balm", p: "$27.20", u: "https://beautyconnectshop.com/products/corthe-revival-balm", img: "https://beautyconnectshop.com/cdn/shop/files/278187643_2747949405500425_8414124959132939917_nlow.jpg?v=1751019934", d: "Breathable moisture shield post-peel/laser. Nourishes without clogging." },
  pureLotion: { n: "Corthe – Pure Lotion", p: "$28.72", u: "https://beautyconnectshop.com/products/corthe-dermo-pure-first-aid-lotion", img: "https://beautyconnectshop.com/cdn/shop/files/Untitleddesign-2024-01-04T162716.031.webp?v=1737150818", d: "First aid for irritated skin. Calms redness, barrier-boosting." },
  eyeNeckCream: { n: "Corthe - De-Aging Eye & Neck Cream", p: "$34.27", u: "https://beautyconnectshop.com/products/corthe-dermo-rejuvenation-de-aging-care-eye-and-neck-cream-40ml", img: "https://beautyconnectshop.com/cdn/shop/files/Eye_and_Neck_Cream.png?v=1749578371", d: "Targets aging signs around eyes and neck specifically." },
  // MASKS
  biocellulose: { n: "KRX - Biocellulose Mask (10 box)", p: "$124.50", u: "https://beautyconnectshop.com/products/krx-treatment-booster-biocellulose-mask-10pcs", img: "https://beautyconnectshop.com/cdn/shop/files/f4f68d_cd015054aae04ed5a1a5dcabb0bbb5a8_mv2.webp?v=1737151439", d: "20ml serum infused. 10x hydration. Coconut fiber acts as second skin." },
  geleeLifting: { n: "KRX - Face Gelee LIFTING COLLAGEN", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-lifting-collagen-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1203.jpg?v=1733527886", d: "Collagen-infused alginate. Firms, lifts, sculpts." },
  geleeHydrating: { n: "KRX - Face Gelee HYDRATING", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-hydrating-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1206.jpg?v=1733527794", d: "Deep moisture lock for dehydrated skin." },
  geleeBrightening: { n: "KRX - Face Gelee BRIGHTENING", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-brightening-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1368.jpg?v=1733527655", d: "Illuminating finish. Pair with Mela Defence protocol." },
  geleeGold: { n: "KRX - Face Gelee GLOWING GOLD", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-glowing-gold-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1367.jpg?v=1733527046", d: "24K gold anti-inflammatory. Luxury wow factor for premium facials." },
  geleeVitC: { n: "KRX - Face Gelee Super VITAMIN C", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-super-astaxanthin-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1202.jpg?v=1733528140", d: "Vitamin C + astaxanthin for antioxidant protection." },
  geleeCocoa: { n: "KRX - Face Gelee VELVET COCOA", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-velvet-cocoa-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1204.jpg?v=1733529998", d: "Cocoa antioxidants + warm texture clients love." },
  geleePumpkin: { n: "KRX - Face Gelee EXFOLIATING PUMPKIN", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-geleeexfoliating-pumpkin-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1205.jpg?v=1733528547", d: "Gentle exfoliation with pumpkin enzymes. Great for dull/congested skin." },
  geleeSpirulina: { n: "KRX - Face Gelee SPIRULINA", p: "$55.00", u: "https://beautyconnectshop.com/products/x-face-gelee-nutritious-sprulina-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1201.jpg?v=1733528049", d: "Nutrient-dense. Feeds depleted skin with vitamins." },
  geleeYouthful: { n: "KRX - Face Gelee YOUTHFUL", p: "$55.00", u: "https://beautyconnectshop.com/products/krx-face-gelee-youthful-modeling-mask", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1208.jpg?v=1733528450", d: "Anti-aging gelee. Perfect finisher for lifting protocols." },
  cicaSheet: { n: "KrX - Cica Sheet Mask (10)", p: "$39.00", u: "https://beautyconnectshop.com/products/krx-cica-sheet-mask", img: "https://beautyconnectshop.com/cdn/shop/files/da6c58_d0527ca516974397bda6310a68c41809_mv2.webp?v=1737147290", d: "Calming cica for post-treatment or sensitive skin." },
  brighteningSheet: { n: "KrX - Brightening Sheet Mask (10)", p: "$39.00", u: "https://beautyconnectshop.com/products/krx-brightening-sheet-mask", img: "https://beautyconnectshop.com/cdn/shop/files/da6c58_96feb4899732460699b497b77915360e_mv2.webp?v=1737147173", d: "Niacinamide-infused for glow after brightening treatments." },
  clearingSheet: { n: "KrX - Clearing Sheet Mask (10)", p: "$39.00", u: "https://beautyconnectshop.com/products/krx-salicylic-acid-sheet-mask", img: "https://beautyconnectshop.com/cdn/shop/files/da6c58_71d965b8d81b4474bf91657a2494ae11_mv2.png?v=1737148571", d: "Salicylic acid sheet mask for acne-prone clients." },
  neoMask: { n: "NeoGenesis Beta Glucan HydroGel Mask (10)", p: "$89.00", u: "https://beautyconnectshop.com/products/neogenesis-beta-glucan-hydrogel-mask", img: "https://beautyconnectshop.com/cdn/shop/files/betamask.jpg?v=1755973123", d: "Beta-glucan from mushrooms. 20x more hydration than HA. For rosacea/eczema." },
  neoSerum: { n: "NeoGenesis HydroGel Beta Glucan Serum (3x15ml)", p: "$92.00", u: "https://beautyconnectshop.com/products/neogenesis-hydro-gel-beta-glucan-serum-3-x-15ml-pre-order", img: "https://beautyconnectshop.com/cdn/shop/files/betaserum.jpg?v=1755973929", d: "Beta-glucan serum for barrier repair. 20x more moisture than HA." },
  omegaMask: { n: "Omega Returning Core Mask Plus", p: "$60.00", u: "https://beautyconnectshop.com/products/omega-returning-core-mask-plus", img: "https://beautyconnectshop.com/cdn/shop/files/657F70B7-A8BC-430A-9B5A-732D0825B433.webp?v=1742941278", d: "Advanced Korean recovery mask for calm, repair and glow." },
  // KITS, RETAIL & EXTRAS
  probioticBundle: { n: "KrX Probiotic Bundle", p: "$101.40", u: "https://beautyconnectshop.com/products/krx-strengthen-protect-probiotic-bundle", img: "https://beautyconnectshop.com/cdn/shop/files/Untitled_design_11_393730ce-17d6-487a-a541-5423f9de0f5c.webp?v=1737155357", d: "Wash + cream bundle. Great retail set for barrier-focused clients." },
  cicaSet: { n: "KRX - Cica All Day Skincare Set", p: "$62.20", u: "https://beautyconnectshop.com/products/krx-cica-recovery-skincare-set", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1139.jpg?v=1737153760", d: "Toner + cleanser + cream set. Easy retail upsell." },
  lipPink: { n: "KRX - Pocket Filler Lip Plumping Gloss PINK", p: "$26.50", u: "https://beautyconnectshop.com/products/krx-pocket-filler-lip-plumping-gloss-pink", img: "https://beautyconnectshop.com/cdn/shop/files/lipplumpingglosspink.webp?v=1749584605", d: "Instant lip plumping. Fun retail add-on clients buy impulsively." },
  lipRouge: { n: "KRX - Pocket Filler Lip Plumping Gloss ROUGE", p: "$26.50", u: "https://beautyconnectshop.com/products/krx-pocket-filler-lip-plumping-gloss-rouge", img: "https://beautyconnectshop.com/cdn/shop/files/lipglossrouge.webp?v=1749584765", d: "Deeper shade for clients who want drama." },
  zenaPremiumKit: { n: "Zena Algae Peel Premium Kit", p: "$849.00", u: "https://beautyconnectshop.com/products/zena-algae-peel-premium-kit", img: "https://beautyconnectshop.com/cdn/shop/files/Zena-peel-Kit_1fd59ec0-d58d-4955-a9c3-186e2c382110.jpg?v=1733516541", d: "20 peels + 100 post-gels + brightening + retinol. Complete system." },
  zenaBasicKit: { n: "Zena Algae Peel Basic Kit", p: "$499.00", u: "https://beautyconnectshop.com/products/zena-algae-peel-basic-kit", img: "https://beautyconnectshop.com/cdn/shop/files/Zena-peel-Kit.jpg?v=1733516457", d: "10 peels + 20 post-gels + brightening + toner + cleanser." },
  exoboost1: { n: "Zena - Exoboost (1 PC)", p: "$149.97", u: "https://beautyconnectshop.com/products/zena-exoboost-1pcs", img: "https://beautyconnectshop.com/cdn/shop/files/5309C061-2A40-45E2-8C89-D3A37759E277.jpg?v=1743226833", d: "Exosome-powered regeneration. Single treatment vial." },
  soothingPads: { n: "Corthe - Soothing Facial Toner Pads", p: "$33.63", u: "https://beautyconnectshop.com/products/corthe-soothing-facial-toner-pads", img: "https://beautyconnectshop.com/cdn/shop/files/46DA1BBB-1B79-401F-AF75-E4FE9FE361D4.jpg?v=1749179021", d: "Pre-soaked calming pads. Perfect post-laser/peel recovery." },
  pfecta: { n: "Pfecta BioCell Solution Set", p: "$105.90", u: "https://beautyconnectshop.com/products/pfecta-biocell-hydra-facial-solution", img: "https://beautyconnectshop.com/cdn/shop/files/IMG-1654.jpg?v=1733533614", d: "Versatile set for hydra facials, jet peels, or as facial spray." },
  zenaCarboxy: { n: "Zena CO2 Mask - Carboxy Therapy", p: "$175.76", u: "https://beautyconnectshop.com/products/zena-co2-mask-carboxy-gel-therapy", img: "https://beautyconnectshop.com/cdn/shop/files/FullSizeRender.jpg?v=1748582271", d: "Two-step carboxy therapy. CO₂ environment for firmer, revitalized skin." },
};

// ─── QUIZ STEPS (8 questions, deeply personalized) ──────────
const STEPS = [
  { id: "concern", q: "What's the #1 skin concern your clients come in for?", sub: "This determines your core product system", opts: [
    { id: "aging", label: "Aging & Volume Loss", desc: "Wrinkles, sagging, hollow areas, loss of firmness" },
    { id: "acne", label: "Acne & Breakouts", desc: "Active acne, congestion, blackheads, scarring" },
    { id: "pigment", label: "Pigmentation & Uneven Tone", desc: "Dark spots, melasma, post-inflammatory marks, dullness" },
    { id: "sensitivity", label: "Sensitivity & Barrier Issues", desc: "Redness, irritation, dehydration, post-procedure recovery" },
  ]},
  { id: "sub", q: "Can you be more specific?", sub: "This narrows down your exact product match", dyn: true },
  { id: "area", q: "Which facial area needs the most attention?", sub: "Different zones require different approaches", opts: [
    { id: "undereye", label: "Under-Eye Area", desc: "Dark circles, hollowing, fine lines" },
    { id: "fullface", label: "Full Face", desc: "Overall treatment across all zones" },
    { id: "jaw", label: "Jawline & Lower Face", desc: "Sagging jowls, nasolabial folds, chin" },
    { id: "forehead", label: "Forehead & Upper Face", desc: "Expression lines, temple hollowing" },
  ]},
  { id: "modality", q: "What treatment tools do you currently use?", sub: "We'll match products compatible with your equipment", opts: [
    { id: "manual", label: "Manual Facials Only", desc: "Hands-on massage, manual extraction" },
    { id: "needling", label: "Microneedling / Nano-needling", desc: "Pen devices, rollers, stamp devices" },
    { id: "devices", label: "Devices (LED, RF, Plasma, Ultrasound)", desc: "Advanced machines" },
    { id: "peels", label: "Chemical Peels & Resurfacing", desc: "Acid peels, herbal peels, enzymes" },
  ]},
  { id: "clientAge", q: "What age group are most of your clients?", sub: "Age affects which actives and systems work best", opts: [
    { id: "young", label: "Under 30", desc: "Prevention, acne, early signs, maintenance" },
    { id: "mid", label: "30–45", desc: "Fine lines, early volume loss, pigmentation starting" },
    { id: "mature", label: "45–60", desc: "Significant volume loss, deep wrinkles, sagging" },
    { id: "senior", label: "60+", desc: "Advanced aging, very thin/fragile skin, sensitivity" },
  ]},
  { id: "goal", q: "What's YOUR #1 business goal right now?", sub: "We'll recommend products that match your growth strategy", opts: [
    { id: "results", label: "Better Treatment Results", desc: "I want my clients to see dramatic visible results" },
    { id: "retail", label: "Grow Retail Revenue", desc: "I want products clients buy to use at home" },
    { id: "menu", label: "Expand My Treatment Menu", desc: "I want new signature treatments to offer" },
    { id: "efficiency", label: "Faster Treatments, More Clients", desc: "I want to optimize time per treatment" },
  ]},
  { id: "setting", q: "What's your practice setup?", sub: "Helps us recommend right product sizes", opts: [
    { id: "solo", label: "Solo / Home Studio", desc: "1 room, 5-15 clients/week" },
    { id: "clinic", label: "Multi-Room Clinic / Med Spa", desc: "2+ rooms, higher volume" },
    { id: "mobile", label: "Mobile / On-Location", desc: "Travel to clients, need portable solutions" },
  ]},
  { id: "budget", q: "What's your monthly product investment budget?", sub: "We'll curate recommendations to fit your range", opts: [
    { id: "starter", label: "Under $300/month", desc: "Building up — essentials first" },
    { id: "mid", label: "$300 – $800/month", desc: "Growing practice — full systems" },
    { id: "premium", label: "$800+/month", desc: "Established — complete professional arsenal" },
  ]},
];

const SUB_OPTS = {
  aging: [
    { id: "volume", label: "Volume Loss & Hollowing", desc: "Sunken temples, flat cheeks, hollow under-eyes" },
    { id: "finelines", label: "Fine Lines & Wrinkles", desc: "Crow's feet, forehead lines, lip lines" },
    { id: "sagging", label: "Sagging & Firmness Loss", desc: "Jawline, jowls, neck laxity" },
    { id: "dullaging", label: "Dull, Tired-Looking Skin", desc: "Lost radiance, rough texture with age" },
  ],
  acne: [
    { id: "active", label: "Active Inflamed Acne", desc: "Pustules, papules, painful breakouts" },
    { id: "congestion", label: "Congestion & Blackheads", desc: "Clogged pores, comedones, oily texture" },
    { id: "scarring", label: "Acne Scarring & Texture", desc: "Ice pick, rolling scars, uneven surface" },
    { id: "hormonal", label: "Hormonal / Recurring Acne", desc: "Chin/jawline, cyclical patterns" },
  ],
  pigment: [
    { id: "darkspots", label: "Sun Damage & Dark Spots", desc: "Age spots, sun spots, freckling" },
    { id: "melasma", label: "Melasma / Hormonal Pigment", desc: "Patchy discoloration, pregnancy mask" },
    { id: "pih", label: "Post-Inflammatory Marks", desc: "Dark marks after acne, injury, treatment" },
    { id: "dull", label: "Overall Dullness & No Glow", desc: "Sallow, lack of radiance, uneven color" },
  ],
  sensitivity: [
    { id: "redness", label: "Redness & Reactive Skin", desc: "Flushing, rosacea-like, easily triggered" },
    { id: "barrier", label: "Compromised Barrier", desc: "Products sting, tight, microbiome imbalance" },
    { id: "postproc", label: "Post-Procedure Recovery", desc: "After peels, laser, needling — fast healing" },
    { id: "dehydrated", label: "Chronic Dehydration", desc: "Dry, flaky, won't hold moisture" },
  ],
};

// ─── RECOMMENDATION ENGINE (exact products with personalized reasons) ──
function getRecs(a) {
  let items = [];
  const add = (product, tag, why) => items.push({ ...product, tag, why });

  // AGING
  if (a.concern === "aging") {
    if (a.sub === "volume") {
      add(P.haFilling, "HERO", "Your clients' #1 need is volume restoration — HA Filling Powder delivers 3 molecular weights of nano HA directly where volume is lost");
      add(P.threadfill, "HERO", "Pair with HA Filling for a complete non-invasive threadlift alternative your clients will rave about");
      if (a.area === "undereye") { add(P.undereyeSol, "ESSENTIAL", "Specifically targets the under-eye area you flagged — meso-grade formula for dark circles + hollowing"); add(P.eyeDarts, "RETAIL", "Easy at-home retail upsell — dissolving microneedle patches your clients can use between visits"); }
      if (a.area === "fullface") add(P.vtoxMask, "ESSENTIAL", "V-Tox contours the full face — jawline, cheeks, forehead — perfect for your full-face approach");
      add(P.carboxySmall, "SUPPORT", "CO₂ therapy boosts circulation before filling — makes HA + Threadfill absorb 2x better");
      if (a.clientAge === "mature" || a.clientAge === "senior") add(P.youthplexSerum, "SUPPORT", "For your mature clients — peptide-powered lifting serum that works daily between professional treatments");
    }
    if (a.sub === "finelines") {
      add(P.threadfill, "HERO", "Collagen threads smooth fine lines from within — visible improvement after first treatment");
      add(P.youthplexSerum, "HERO", "Lightweight serum your clients can use daily for cumulative line-smoothing");
      add(P.youthplexCream, "SUPPORT", "Pairs with the serum — firms and sculpts as an AM/PM finishing step");
      if (a.modality === "needling") add(P.mtsPrep, "ESSENTIAL", "Essential prep kit for your microneedling treatments — exfoliant + neutralizer");
      add(P.eyeCream, "RETAIL", "31 active ingredients for crow's feet. Top retail seller for anti-aging clients");
    }
    if (a.sub === "sagging") {
      add(P.vtoxMask, "HERO", "Peel-off contouring mask specifically designed for V-line and jawline definition");
      add(P.threadfill, "HERO", "Absorbable collagen threads create a lifting scaffold in sagging tissue");
      add(P.carboxyLarge, "SUPPORT", a.setting === "clinic" ? "20-treatment bulk — cost-effective for your multi-room clinic volume" : "CO₂ boosts circulation and preps skin for maximum threadfill absorption");
      if (a.modality === "devices") add(P.exoboost1, "ADVANCED", "Exosome-powered regeneration — the most advanced treatment in our catalog for sagging");
    }
    if (a.sub === "dullaging") {
      add(P.glowSerum, "HERO", "Vitamin C serum restores the radiance your aging clients have lost");
      add(P.r3Peel, "HERO", "Retinol-based resurfacing accelerates cell turnover — reveals fresh, luminous skin");
      add(P.glowToner, "SUPPORT", "Prep toner that primes skin for brightening actives — doubles serum absorption");
      add(P.essencePads, "SUPPORT", "Quick hydration between treatment steps — keeps skin dewy during protocol");
    }
    // Mask based on concern
    if (a.sub === "volume" || a.sub === "sagging") add(P.geleeLifting, "MASK", "Collagen-infused alginate mask seals in all lifting actives — the perfect protocol finisher");
    if (a.sub === "finelines") add(P.geleeYouthful, "MASK", "Anti-aging gelee specifically formulated for fine line treatment protocols");
    if (a.sub === "dullaging") add(P.geleeGold, "MASK", "24K gold mask — anti-inflammatory + luxury wow factor. Your clients will feel pampered");
    add(P.biocellulose, "MASK", "20ml serum infused coconut fiber — 10x hydration. Essential post-treatment finisher");
    // Retail based on goal
    if (a.goal === "retail") { add(P.youthplexCream, "RETAIL", "Top retail seller for aging clients. They'll reorder monthly"); add(P.lipPink, "RETAIL", "Impulse buy add-on — lip plumping gloss clients grab at checkout"); }
  }

  // ACNE
  if (a.concern === "acne") {
    if (a.sub === "active") {
      add(P.pd13, "HERO", "Advanced peptide delivery designed specifically for active acne repair and deep regeneration");
      add(P.inflacure, "HERO", "Anti-inflammatory concentrate — apply directly on extracted areas for rapid calming");
      add(P.preExtraction, "SUPPORT", "Softens comedones so extractions are easier, faster, and less traumatic for clients");
      add(P.probioticWash, "SUPPORT", "Tri-probiotic cleanser rebuilds skin microbiome — prevents recurring breakouts");
    }
    if (a.sub === "congestion") {
      add(P.preExtraction, "HERO", "Your #1 tool for stubborn blackheads — softens them for painless extraction");
      add(P.bioherb, "HERO", "50-herb blend resurfaces without harsh chemicals — gentle enough for regular congestion treatments");
      add(P.oxyPumpkin, "SUPPORT", "Pumpkin enzyme cleanser dissolves dead cells that cause congestion — clients love the bubble texture");
      add(P.cryoCaps, "SUPPORT", "Post-extraction cryo tightens pores instantly — dramatic visible results");
    }
    if (a.sub === "scarring") {
      add(P.greenSea, "HERO", "The most intensive peel for texture — herbal resurfacing breaks down scar tissue");
      add(P.haFilling, "HERO", "Nano HA fills sunken acne scars from beneath — immediate visible smoothing");
      if (a.modality === "needling") add(P.mtsPrep, "ESSENTIAL", "Prep kit for your microneedling — essential before treating acne scars");
      add(P.threadfill, "SUPPORT", "Collagen stimulation helps rebuild tissue where scars have created depressions");
    }
    if (a.sub === "hormonal") {
      add(P.pd13, "HERO", "PD-13 works on the deeper inflammatory cycle — not just surface symptoms");
      add(P.probioticWash, "HERO", "Microbiome restoration is key for hormonal acne — rebalances skin flora");
      add(P.probioticCream, "SUPPORT", "Complete the probiotic protocol — cream maintains flora balance between visits");
      add(P.inflacure, "SUPPORT", "Calms the inflammation cycle that drives hormonal breakouts");
    }
    add(P.clearingSheet, "MASK", "Salicylic acid sheet mask — continue clearing action while client relaxes");
    if (a.sub === "scarring") add(P.biocellulose, "MASK", "Post-treatment healing mask — coconut fiber doesn't tug on compromised skin");
    add(P.aftercareCream, "RETAIL", "Individual sachets to send home — essential post-extraction healing for every client");
    if (a.goal === "retail") add(P.pureSpot, "RETAIL", "Overnight spot treatment — clients use at home between appointments. High reorder rate");
  }

  // PIGMENTATION
  if (a.concern === "pigment") {
    if (a.sub === "darkspots") {
      add(P.melaSerum, "HERO", "Tranexamic Acid + Niacinamide — clinically proven to inhibit melanin and fade dark spots");
      add(P.melaCream, "HERO", "Daily brightening cream maintains results between treatments — prevents spots from returning");
      add(P.cortheOxyPeel, "SUPPORT", "No-downtime brightening peel that specifically targets existing pigmentation");
      add(P.cortheBrightC, "SUPPORT", "Vitamin C concentrate for antioxidant defence — prevents new spots forming");
    }
    if (a.sub === "melasma") {
      add(P.melaSerum, "HERO", "Tranexamic Acid is the gold standard for melasma — inhibits melanin at the source");
      add(P.cortheIonTo, "HERO", "Botanic placenta ampoule — clinical-grade brightening especially effective for hormonal pigment");
      add(P.cortheSpot, "SUPPORT", "Targeted treatment for stubborn melasma patches that resist general brightening");
      add(P.cortheOxyPeel, "SUPPORT", "Gentle oxy peel won't trigger rebound pigmentation — safe for melasma clients");
    }
    if (a.sub === "pih") {
      add(P.melaSerum, "HERO", "Fades post-inflammatory marks faster — Niacinamide calms while Tranexamic lightens");
      add(P.inflacure, "SUPPORT", "Addresses the underlying inflammation that CAUSES post-inflammatory hyperpigmentation");
      add(P.zenaBrightening, "SUPPORT", "Professional-grade brightening serum for stubborn PIH marks");
      add(P.cortheBrightC, "SUPPORT", "Vitamin C accelerates mark fading and evens overall tone");
    }
    if (a.sub === "dull") {
      add(P.glowSerum, "HERO", "Vitamin C serum restores that glass-skin glow your clients are asking for");
      add(P.r3Peel, "HERO", "Retinol resurfacing reveals fresh, luminous skin beneath the dull layer");
      add(P.glowToner, "SUPPORT", "Quenching toner preps skin and doubles the absorption of brightening actives");
      add(P.zenaBrightening, "SUPPORT", "Professional brightening targets uneven tone for uniform radiance");
    }
    if (a.sub === "darkspots" || a.sub === "melasma") add(P.geleeBrightening, "MASK", "Illuminating alginate mask — seals in brightening actives for maximum absorption");
    else add(P.geleeGold, "MASK", "24K gold mask delivers anti-inflammatory radiance boost — instant wow for dull clients");
    add(P.brighteningSheet, "MASK", "Niacinamide sheet mask for continued brightening while clients relax");
    if (a.goal === "retail") { add(P.melaCream, "RETAIL", "Daily brightening cream for home use — clients need this to maintain in-clinic results"); add(P.cortheBrightCream, "RETAIL", "Corthe brightening moisturizer — great alternative for sensitive skin clients"); }
  }

  // SENSITIVITY
  if (a.concern === "sensitivity") {
    if (a.sub === "redness") {
      add(P.cortheCica, "HERO", "Centella asiatica concentrate — the #1 ingredient for calming chronic redness");
      add(P.cortheRelief, "HERO", "Relief ampoule calms reactive skin on contact — immediate soothing effect");
      add(P.cortheCleansingMilk, "SUPPORT", "pH-balanced milk cleanser won't trigger reactive skin like foaming cleansers do");
      add(P.neoSerum, "SUPPORT", "Beta-glucan from mushrooms — 20x more hydration than HA, calms inflammation");
    }
    if (a.sub === "barrier") {
      add(P.probioticWash, "HERO", "Tri-probiotic complex rebuilds the microbiome your compromised clients desperately need");
      add(P.probioticCream, "HERO", "Completes the probiotic protocol — restores healthy skin flora daily");
      add(P.cortheBifida, "SUPPORT", "Bifida ferment lysate strengthens the barrier from within");
      add(P.cortheCica, "SUPPORT", "Centella extract supports the structural rebuilding of a damaged barrier");
    }
    if (a.sub === "postproc") {
      add(P.biocellulose, "HERO", "Coconut fiber mask doesn't tug compromised skin — most gentle mask option. Must-have post-procedure");
      add(P.cicaCream, "HERO", "Ceramide + centella formula for rapid post-treatment barrier restoration");
      add(P.aftercareCream, "ESSENTIAL", "Individual sachets to send home with every client — essential post-procedure recovery");
      add(P.soothingPads, "SUPPORT", "Pre-soaked calming pads — instant soothing post-laser, peel, or needling");
      add(P.jellyMist, "SUPPORT", "Spray-on gel mask between steps — 6 hours of nutrient delivery with zero irritation");
    }
    if (a.sub === "dehydrated") {
      add(P.zenaHyalnano, "HERO", "Nano HA penetrates deeper than standard hyaluronic acid — real deep-layer hydration");
      add(P.haFilling, "HERO", "HA Filling Powder isn't just for anti-aging — it fills dehydrated skin with 3 HA molecular weights");
      add(P.cortheMoisture, "SUPPORT", "Long-lasting hydration cream without greasy residue — clients can use daily");
      add(P.jellyMist, "SUPPORT", "Spray-on hydration that delivers 20x more moisture than sheet masks");
    }
    if (a.sub === "redness") add(P.neoMask, "MASK", "Beta-glucan hydrogel mask calms rosacea, eczema, dermatitis — instantly cools reactive skin");
    else add(P.cicaSheet, "MASK", "Cica sheet mask soothes without irritation — safe for even the most compromised skin");
    add(P.biocellulose, "MASK", "Biocellulose acts like a second skin — delivers 20ml of hydrating serum without pulling or drying");
    if (a.goal === "retail") { add(P.probioticBundle, "RETAIL", "Probiotic wash + cream bundle — clients rebuild their barrier at home between visits"); add(P.cicaSet, "RETAIL", "Cica skincare set — toner + cleanser + cream. Easy retail upsell for sensitive skin clients"); }
    add(P.revivalBalm, "RETAIL", "Post-treatment balm creates breathable moisture shield. Clients love using it at home");
  }

  // Budget filter
  if (a.budget === "starter") items = items.filter((_, i) => i < 5);
  if (a.budget === "mid") items = items.filter((_, i) => i < 8);

  // Deduplicate
  const seen = new Set();
  return items.filter(item => { if (seen.has(item.n)) return false; seen.add(item.n); return true; });
}

// ─── UI COMPONENTS ──────────────────────────────────────────
const GoldLine = () => <div style={{ width: 60, height: 1, background: `linear-gradient(90deg, transparent, ${B.gold}, transparent)`, margin: "14px auto" }} />;

const Card = ({ item }) => (
  <a href={item.u} target="_blank" rel="noopener noreferrer" style={{ display: "flex", gap: 12, padding: 14, background: "white", border: `1px solid ${B.lgold}`, borderRadius: 10, textDecoration: "none", transition: "all 0.2s", alignItems: "flex-start" }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = B.gold; e.currentTarget.style.transform = "translateY(-1px)"; e.currentTarget.style.boxShadow = `0 4px 16px ${B.gold}22`; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = B.lgold; e.currentTarget.style.transform = "none"; e.currentTarget.style.boxShadow = "none"; }}>
    {item.img && <img src={item.img} alt="" style={{ width: 60, height: 60, objectFit: "cover", borderRadius: 8, background: "#f5f0eb", flexShrink: 0 }} onError={e => e.target.style.display = "none"} />}
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "Helvetica, sans-serif", fontSize: 9, letterSpacing: 1, padding: "2px 7px", borderRadius: 3, background: item.tag === "HERO" ? B.gold : item.tag === "ESSENTIAL" ? B.dark : item.tag === "RETAIL" ? "#E8D5C0" : B.lgold, color: item.tag === "ESSENTIAL" ? B.cream : B.dark, flexShrink: 0 }}>{item.tag}</span>
        <span style={{ fontFamily: "Georgia, serif", fontSize: 13, color: B.dark, fontWeight: 600, lineHeight: 1.3 }}>{item.n}</span>
      </div>
      <p style={{ fontFamily: "Georgia, serif", fontSize: 11, color: B.gray, margin: "4px 0 6px", lineHeight: 1.5, fontStyle: "italic" }}>{item.why}</p>
      <span style={{ fontFamily: "Helvetica, sans-serif", fontSize: 12, color: B.gold, fontWeight: 700 }}>{item.p}</span>
    </div>
    <span style={{ fontSize: 14, color: B.gray, flexShrink: 0, marginTop: 4 }}>→</span>
  </a>
);

// ─── MAIN APP ───────────────────────────────────────────────
export default function App() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [email, setEmail] = useState(""); const [name, setName] = useState(""); const [biz, setBiz] = useState("");
  const [phase, setPhase] = useState("quiz");
  const [fade, setFade] = useState(true);

  const cur = STEPS[step];
  const opts = cur?.dyn ? (SUB_OPTS[answers.concern] || []) : (cur?.opts || []);

  const select = (id) => { setFade(false); setTimeout(() => { setAnswers({ ...answers, [cur.id]: id }); if (step < STEPS.length - 1) setStep(step + 1); else setPhase("gate"); setFade(true); }, 150); };

  const results = phase === "results" ? getRecs(answers) : [];

  const handleGateSubmit = () => {
    if (!email.trim()) return;
    const recs = getRecs(answers);
    sendToKlaviyo(email.trim(), name.trim(), biz.trim(), answers, recs);
    setPhase("results");
  };

  return (
    <div style={{ minHeight: "100vh", background: B.cream, fontFamily: "Georgia, serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&display=swap" rel="stylesheet" />

      {/* HEADER */}
      <div style={{ textAlign: "center", padding: "28px 20px 20px" }}>
        <p style={{ fontFamily: "Helvetica, sans-serif", fontSize: 10, letterSpacing: 4, color: B.gray, textTransform: "uppercase", margin: 0 }}>Beauty Connect Pro</p>
        <h1 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 24, color: B.dark, margin: "6px 0", fontWeight: 400 }}>Find Your Perfect Protocol</h1>
        <p style={{ fontSize: 12, color: B.gray, margin: 0 }}>8 quick questions → personalized product recommendations with direct shop links</p>
        <GoldLine />
      </div>

      <div style={{ maxWidth: 560, margin: "0 auto", padding: "0 20px 48px" }}>

        {/* RESULTS */}
        {phase === "results" && <>
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <p style={{ fontFamily: "Helvetica, sans-serif", fontSize: 10, letterSpacing: 3, color: B.gold, textTransform: "uppercase", margin: "0 0 4px" }}>
              {name ? `${name}'s` : "Your"} Personalized Recommendation
            </p>
            <h2 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 20, color: B.dark, margin: "0 0 4px", fontWeight: 400 }}>
              {answers.concern === "aging" ? "Anti-Aging" : answers.concern === "acne" ? "Acne Management" : answers.concern === "pigment" ? "Brightening" : "Sensitivity"} Protocol
            </h2>
            <p style={{ fontSize: 11, color: B.gray }}>
              {SUB_OPTS[answers.concern]?.find(s => s.id === answers.sub)?.label} · {STEPS[4].opts.find(o => o.id === answers.clientAge)?.label} clients · {STEPS[5].opts.find(o => o.id === answers.goal)?.label}
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {results.map((item, i) => <Card key={i} item={item} />)}
          </div>

          <div style={{ textAlign: "center", marginTop: 24 }}>
            <a href="https://beautyconnectshop.com" target="_blank" rel="noopener noreferrer" style={{ display: "inline-block", fontFamily: "Helvetica, sans-serif", fontSize: 11, letterSpacing: 2, padding: "12px 32px", background: B.dark, color: B.gold, textDecoration: "none", borderRadius: 4, textTransform: "uppercase" }}>Shop All Products →</a>
            <p style={{ fontSize: 11, color: B.gray, marginTop: 12 }}>Questions about protocols? Email Maria at beautyconnect.info@gmail.com</p>
            <button onClick={() => { setStep(0); setAnswers({}); setPhase("quiz"); setEmail(""); setName(""); setBiz(""); }} style={{ fontSize: 11, color: B.gray, background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>Retake Quiz</button>
          </div>
        </>}

        {/* EMAIL GATE */}
        {phase === "gate" && (
          <div style={{ textAlign: "center", maxWidth: 400, margin: "20px auto 0" }}>
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: B.dark, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px", fontSize: 18, color: B.gold }}>✧</div>
            <h2 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 20, color: B.dark, margin: "0 0 6px", fontWeight: 400 }}>Your custom results are ready!</h2>
            <p style={{ fontSize: 13, color: B.gray, lineHeight: 1.6, marginBottom: 20 }}>Enter your details to see your exact product matches with prices and direct shop links. We'll also email you a PDF protocol card.</p>
            {[
              { ph: "First name", v: name, set: setName },
              { ph: "Business / clinic name", v: biz, set: setBiz },
              { ph: "Your email address", v: email, set: setEmail },
            ].map((f, i) => (
              <input key={i} type={i === 2 ? "email" : "text"} placeholder={f.ph} value={f.v} onChange={e => f.set(e.target.value)}
                onKeyDown={e => e.key === "Enter" && i === 2 && handleGateSubmit()}
                style={{ width: "100%", boxSizing: "border-box", fontSize: 14, padding: "11px 16px", border: `1px solid ${B.lgold}`, borderRadius: 4, marginBottom: 10, outline: "none", color: B.dark, background: "white" }} />
            ))}
            <button onClick={handleGateSubmit} style={{ width: "100%", fontFamily: "Helvetica, sans-serif", fontSize: 11, letterSpacing: 2, padding: "13px 0", background: email.trim() ? B.dark : "#ccc", color: email.trim() ? B.gold : "#888", border: "none", borderRadius: 4, cursor: email.trim() ? "pointer" : "default", textTransform: "uppercase", marginTop: 4 }}>See My Recommendations</button>
            <p style={{ fontSize: 10, color: B.gray, marginTop: 10 }}>For licensed professionals only. We respect your privacy.</p>
          </div>
        )}

        {/* QUIZ */}
        {phase === "quiz" && <>
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontFamily: "Helvetica, sans-serif", fontSize: 10, color: B.gray, letterSpacing: 1 }}>STEP {step + 1} OF {STEPS.length}</span>
              <span style={{ fontFamily: "Helvetica, sans-serif", fontSize: 10, color: B.gold }}>{Math.round(((step + 1) / STEPS.length) * 100)}%</span>
            </div>
            <div style={{ height: 2, background: B.lgold, borderRadius: 1 }}><div style={{ height: 2, background: B.gold, borderRadius: 1, width: `${((step + 1) / STEPS.length) * 100}%`, transition: "width 0.4s" }} /></div>
          </div>

          <div style={{ opacity: fade ? 1 : 0, transition: "opacity 0.15s" }}>
            <h2 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 19, color: B.dark, margin: "0 0 4px", fontWeight: 400, lineHeight: 1.4 }}>{cur?.q}</h2>
            <p style={{ fontSize: 12, color: B.gray, margin: "0 0 18px" }}>{cur?.sub}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {opts.map(o => (
                <button key={o.id} onClick={() => select(o.id)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", background: "white", border: `1px solid ${B.lgold}`, borderRadius: 8, cursor: "pointer", textAlign: "left", transition: "all 0.15s" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = B.gold; e.currentTarget.style.background = "#FDFBF8"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = B.lgold; e.currentTarget.style.background = "white"; }}>
                  <div>
                    <span style={{ fontSize: 14, color: B.dark, display: "block", fontWeight: 600 }}>{o.label}</span>
                    {o.desc && <span style={{ fontSize: 11, color: B.gray, marginTop: 2, display: "block", lineHeight: 1.4 }}>{o.desc}</span>}
                  </div>
                </button>
              ))}
            </div>
            {step > 0 && <button onClick={() => { setFade(false); setTimeout(() => { setStep(step - 1); setFade(true); }, 150); }} style={{ fontSize: 11, color: B.gray, background: "none", border: "none", cursor: "pointer", display: "block", margin: "14px auto 0" }}>← Back</button>}
          </div>
        </>}
      </div>

      <div style={{ textAlign: "center", padding: "16px 20px 28px", borderTop: `1px solid ${B.lgold}` }}>
        <p style={{ fontSize: 10, color: B.gray, margin: 0 }}>© 2025 Beauty Connect Pro · Edmonton, Alberta · beautyconnectshop.com</p>
      </div>
    </div>
  );
}
