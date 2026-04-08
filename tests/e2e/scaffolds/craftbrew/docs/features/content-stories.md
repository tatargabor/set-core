# Content & Stories Feature

> **Figma frames:** Stories — see [design-system.md](../design/design-system.md#frame-mapping)

## Stories Section

Blog-like content section, but structured — every article is linked to a category and products.

### Categories

| Category | Slug | Icon | Description |
|---|---|---|---|
| Origin Stories | eredet | Globe | Where does your coffee come from? A journey to the farms. |
| Roasting | porkoles | Flame | The art and science of roasting. |
| Brewing Guides | fozes | Coffee | Brew the perfect cup. |
| Health & Science | egeszseg | Heart | What does science say about coffee? |
| Gift Ideas | ajandek | Gift | Gift ideas for coffee lovers. |

### Story List Page

```
┌─────────────────────────────────────────────────────────┐
│  Stories                                                 │
│                                                          │
│  [All] [Origin Stories] [Roasting] [Brewing]            │
│  [Health] [Gift Ideas]                                   │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ ░░░░░░░░ │ │ ░░░░░░░░ │ │ ░░░░░░░░ │                │
│  │ ░ COVER  ░│ │ ░ COVER  ░│ │ ░ COVER  ░│                │
│  │ ░░░░░░░░ │ │ ░░░░░░░░ │ │ ░░░░░░░░ │                │
│  │          │ │          │ │          │                │
│  │ Origin   │ │ Brewing  │ │ Health   │                │
│  │ Yirgach. │ │ V60 pour │ │ The      │                │
│  │ The      │ │ over     │ │ benefits │                │
│  │ birth-   │ │ step by  │ │ of       │                │
│  │ place    │ │ step     │ │ coffee   │                │
│  │ 2026-03  │ │ 2026-02  │ │ 2026-01  │                │
│  └──────────┘ └──────────┘ └──────────┘                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Story Details Page

```
┌─────────────────────────────────────────────────────────┐
│  [Origin Stories]                                        │
│                                                          │
│  Yirgacheffe: The Birthplace of Coffee                  │
│  CraftBrew Team — March 1, 2026                         │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │                    COVER IMAGE                        ││
│  │         (Ethiopian coffee plantation landscape)       ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  [Article content — 3-5 paragraphs...]                   │
│                                                          │
│  ── Related Products ───────────────────────────────    │
│  [Ethiopia Yirgacheffe]  [Discover Africa bundle]       │
│                                                          │
│  ── Share ─────────────────────────────────────────     │
│  [Facebook] [Twitter/X] [Copy link]                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Mobile

- Story cards in 1 column layout
- Content text remains readable at mobile widths
- Images maintain aspect ratio, no distortion

## Seed Stories (10 items)

Every story has HU and EN content. Each seed must contain at least 2-3 paragraphs of actual text (not lorem ipsum!).

### 1. "Yirgacheffe: The Birthplace of Coffee" (Origin Stories)
- **Related products:** K1 Ethiopia Yirgacheffe, B2 Discover Africa
- **Content outline:** Ethiopia as the birthplace of coffee, the uniqueness of the Yirgacheffe region, the washed processing tradition, the story of local farmers.

### 2. "Colombia Huila — At the Foot of the Volcano" (Origin Stories)
- **Related products:** K2 Colombia Huila, B1 Starter Pack
- **Content outline:** The volcanic soil of Huila county, advantages of high-altitude cultivation, Colombian coffee culture and the role of small farms.

### 3. "Brazil Cerrado — Treasure of the Savanna" (Origin Stories)
- **Related products:** K3 Brazil Cerrado
- **Content outline:** The climate of the Cerrado region, the natural processing method, why this coffee is so full-bodied and creamy.

### 4. "How We Roast — Behind the Scenes at Our Roastery" (Roasting)
- **Related products:** K3 Brazil (dark), K1 Ethiopia (light), K2 Colombia (medium)
- **Content outline:** Steps of the roasting process, the role of temperature and time, first crack / second crack, why light/medium/dark are different.

### 5. "Light vs Dark: Which Should You Choose?" (Roasting)
- **Related products:** K1 Ethiopia (light), K3 Brazil (dark), K7 Costa Rica (medium)
- **Content outline:** The effect of roast level on flavor, acidity, and caffeine content. When to choose which, which brewing method suits which.

### 6. "V60 Pour-Over — Step by Step" (Brewing Guides)
- **Related products:** E1 V60, E2 V60 Filter, E6 Scale, E7 Kettle, K1 Ethiopia
- **Content outline:** Required equipment, water-to-coffee ratio (1:15), water temperature (92-96°C), pouring technique, timing (3:30-4:00 minutes).

### 7. "French Press Masterclass" (Brewing Guides)
- **Related products:** E5 French Press, E3 Timemore Grinder, K3 Brazil, K6 Sumatra
- **Content outline:** Importance of coarse grinding, 4-minute steeping, coffee-to-water ratio (1:12), why full-bodied coffees work best here.

### 8. "AeroPress Recipes for Advanced Brewers" (Brewing Guides)
- **Related products:** E4 AeroPress, K5 Kenya, K8 Rwanda
- **Content outline:** Standard vs inverted method, competition recipes, pressure and time experimentation, why specialty coffee champions love it.

### 9. "The Benefits of Coffee — What Does Science Say?" (Health & Science)
- **Related products:** (no specific products, general shop link)
- **Content outline:** Antioxidants, cognitive functions, sports performance, recommended daily intake, when to drink coffee and when not to.

### 10. "Coffee Gifts Under 5, 10, and 20 Thousand" (Gift Ideas)
- **Related products:** B4 Gift for Coffee Lovers, B1 Starter Pack, B3 Pro Barista, M4 Gift Card
- **Content outline:** Budget-based gift ideas, bundle and gift card combos, what to consider when buying coffee as a gift.

## Design Reference

Use exact values from `docs/design-system.md` — do NOT use framework defaults.

**Key colors**: primary `#78350F`, secondary `#D97706`, background `#FFFBEB`
**Fonts**: Playfair Display, Inter, JetBrains Mono

**Matched pages:**
- **Catalog**: see design-system.md § Page Layouts
- **Stories**: Uses: figma
- **Search**: see design-system.md § Page Layouts
