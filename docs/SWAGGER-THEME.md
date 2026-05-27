# Swagger UI - Pink Pastel Theme

> **Primary Color:** `#ef1061` (Hot Pink)
> **Style:** Pastel, Soft, Modern
> **Last Updated:** 2026-05-19

---

## 🎨 Color Palette

### Primary Colors
| Color | Hex | Usage |
|-------|-----|-------|
| **Hot Pink** | `#ef1061` | Primary brand color, buttons, highlights |
| **Dark Pink** | `#c70d4f` | Gradients, hover states |
| **Deep Pink** | `#831843` | Text, dark accents |
| **Darker Pink** | `#5c0d2e` | Strong emphasis |

### Pastel Shades
| Color | Hex | Usage |
|-------|-----|-------|
| **Light Pink** | `#ffc2dd` | Borders, light accents |
| **Soft Pink** | `#ffb3d9` | Backgrounds, headers |
| **Pale Pink** | `#fff5f9` | Page background, cards |
| **Blush Pink** | `#fff0f6` | Sections, containers |
| **Rose Pink** | `#ffe4f0` | Gradient backgrounds |

### HTTP Method Colors (Pink Palette)
| Method | Border | Background | Badge | Text |
|--------|--------|------------|-------|------|
| **GET** | `#ffc2dd` | `#fff5f9` | `#ffb3d9` | `#831843` |
| **POST** | `#ff9ec4` | `#fff0f6` | `#ff7ab0` | `#5c0d2e` |
| **PUT** | `#ffd4e5` | `#fffafc` | `#ffadd2` | `#6b1039` |
| **DELETE** | `#ef1061` | `#fff0f6` | `#ef1061` | `white` |
| **PATCH** | `#ff85b8` | `#fff5f9` | `#ff5c9d` | `white` |

---

## 🎯 Design Features

### 1. Header Banner
- **Background:** Gradient from `#ffc2dd` to `#ffb3d9`
- **Border:** 3px solid `#ef1061`
- **Title:** Gradient text `#ef1061` → `#c70d4f`
- **Shadow:** `rgba(239, 16, 97, 0.15)`

### 2. Operation Blocks
- **Border:** 2px solid (varies by method)
- **Border Radius:** 12px
- **Hover Effect:**
  - Shadow: `rgba(239, 16, 97, 0.12)`
  - Transform: `translateY(-2px)`

### 3. Buttons
- **Execute Button:**
  - Background: Gradient `#ef1061` → `#c70d4f`
  - Shadow: `rgba(239, 16, 97, 0.3)`
  - Hover: Lift effect with stronger shadow

- **Try It Out Button:**
  - Background: `#fff0f6`
  - Border: 2px solid `#ff9ec4`
  - Hover: Background `#ffc2dd`

### 4. Input Fields
- **Border:** 2px solid `#ffc2dd`
- **Focus:**
  - Border: `#ef1061`
  - Shadow: `rgba(239, 16, 97, 0.1)`

### 5. Code Blocks
- **Background:** `#2d1b2e` (dark pink-tinted)
- **Border:** 2px solid `#ef1061`
- **Text Color:** `#ffc2dd`

### 6. Scrollbar
- **Track:** `#fff5f9`
- **Thumb:** `#ff9ec4`
- **Thumb Hover:** `#ef1061`

---

## 📐 Typography

### Fonts
- **UI Text:** Inter (Google Fonts)
- **Code:** Fira Code (Google Fonts)

### Font Weights
- **Regular:** 400
- **Medium:** 500
- **Semibold:** 600
- **Bold:** 700

---

## 🔧 Customization Guide

### Change Primary Color

Edit `scripts/build-swagger-ui.js`:

```javascript
// Find and replace #ef1061 with your color
// Example locations:
// - Line ~35: Header border
// - Line ~40: Title gradient
// - Line ~90: DELETE method
// - Line ~150: Buttons
// - Line ~180: Input focus
```

### Adjust Pastel Intensity

To make colors lighter/darker:

```css
/* Lighter (more pastel) */
background: #fff8fb; /* instead of #fff5f9 */
border-color: #ffd9ea; /* instead of #ffc2dd */

/* Darker (more vibrant) */
background: #ffe4f0; /* instead of #fff5f9 */
border-color: #ff9ec4; /* instead of #ffc2dd */
```

### HTTP Method Color Override

```css
/* Example: Make GET method use green */
.swagger-ui .opblock.opblock-get {
  border-color: #a7f3d0;
  background: #f0fdf4;
}

.swagger-ui .opblock.opblock-get .opblock-summary-method {
  background: #6ee7b7;
  color: #065f46;
}
```

---

## 🚀 Build & Deploy

### Build Documentation
```bash
npm run build:docs
```

### Preview Locally
```bash
# Open in browser
xdg-open api-docs.html

# Or serve with Python
python3 -m http.server 8000
# Then open: http://localhost:8000/api-docs.html
```

### Deploy to GitHub Pages
```bash
git add scripts/build-swagger-ui.js
git commit -m "feat(docs): update to pink pastel theme"
git push origin main
```

GitHub Actions will automatically build and deploy.

---

## 🎨 Color Psychology

**Pink (#ef1061)** conveys:
- ✨ **Creativity** - Innovative, modern approach
- 💖 **Friendliness** - Approachable, welcoming
- 🎯 **Energy** - Dynamic, vibrant
- 🌸 **Softness** - Gentle, non-threatening (pastel shades)

Perfect for:
- Customer-facing APIs
- Creative/design tools
- Community platforms
- Modern SaaS products

---

## 📸 Screenshots

### Before (Purple Pastel)
- Primary: `#7c3aed` (Purple)
- Style: Cool, professional

### After (Pink Pastel)
- Primary: `#ef1061` (Hot Pink)
- Style: Warm, energetic, modern

---

## 🔗 Resources

- [Swagger UI Documentation](https://swagger.io/tools/swagger-ui/)
- [Color Palette Generator](https://coolors.co/)
- [Google Fonts](https://fonts.google.com/)
- [CSS Gradient Generator](https://cssgradient.io/)

---

**Created by:** Kiro AI Assistant
**Version:** 1.0.0
**License:** MIT
