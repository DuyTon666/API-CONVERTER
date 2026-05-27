const fs = require("fs");
const path = require("path");

// Đọc OpenAPI bundled spec
const openapiSpec = fs.readFileSync(
  "dist/openapi-bundled.yaml",
  "utf8"
);

// HTML template với Swagger UI và Pastel Theme
const html = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>P.A DEV API Documentation</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.11.0/favicon-32x32.png" sizes="32x32" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.11.0/favicon-16x16.png" sizes="16x16" />

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">

  <style>
    /* ═══════════════════════════════════════════════════════════
       PASTEL THEME - Swagger UI Custom Styling
       ═══════════════════════════════════════════════════════════ */

    * {
      box-sizing: border-box;
    }

    html {
      box-sizing: border-box;
      overflow: -moz-scrollbars-vertical;
      overflow-y: scroll;
    }

    body {
      margin: 0;
      padding: 0;
      background: linear-gradient(135deg, #fef5ff 0%, #f0f9ff 100%);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Custom Header Banner ── */
    .custom-header {
      background: linear-gradient(135deg, #e9d5ff 0%, #dbeafe 100%);
      border-bottom: 2px solid #c4b5fd;
      padding: 20px 40px;
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.1);
    }

    .custom-header h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 700;
      background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.5px;
    }

    .custom-header p {
      margin: 8px 0 0 0;
      color: #6b7280;
      font-size: 14px;
      font-weight: 400;
    }

    .custom-header .version-badge {
      display: inline-block;
      background: #fef3c7;
      color: #92400e;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      margin-left: 12px;
      border: 1px solid #fcd34d;
    }

    /* ── Swagger UI Container ── */
    #swagger-ui {
      max-width: 1400px;
      margin: 0 auto;
      padding: 40px 20px;
    }

    /* ── Info Section ── */
    .swagger-ui .info {
      margin: 30px 0;
      padding: 30px;
      background: white;
      border-radius: 16px;
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.08);
      border: 1px solid #e9d5ff;
    }

    .swagger-ui .info .title {
      font-size: 32px;
      font-weight: 700;
      color: #7c3aed;
      margin-bottom: 12px;
    }

    .swagger-ui .info .description {
      color: #6b7280;
      line-height: 1.7;
      font-size: 15px;
    }

    /* ── Operation Blocks ── */
    .swagger-ui .opblock {
      margin: 20px 0;
      border-radius: 12px;
      border: 2px solid;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
      overflow: hidden;
      transition: all 0.2s ease;
    }

    .swagger-ui .opblock:hover {
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
      transform: translateY(-2px);
    }

    /* ── HTTP Method Colors (Pastel) ── */
    .swagger-ui .opblock.opblock-get {
      border-color: #a7f3d0;
      background: #f0fdf4;
    }

    .swagger-ui .opblock.opblock-get .opblock-summary-method {
      background: #6ee7b7;
      color: #065f46;
    }

    .swagger-ui .opblock.opblock-post {
      border-color: #bfdbfe;
      background: #eff6ff;
    }

    .swagger-ui .opblock.opblock-post .opblock-summary-method {
      background: #93c5fd;
      color: #1e3a8a;
    }

    .swagger-ui .opblock.opblock-put {
      border-color: #fed7aa;
      background: #fffbeb;
    }

    .swagger-ui .opblock.opblock-put .opblock-summary-method {
      background: #fdba74;
      color: #7c2d12;
    }

    .swagger-ui .opblock.opblock-delete {
      border-color: #fecaca;
      background: #fef2f2;
    }

    .swagger-ui .opblock.opblock-delete .opblock-summary-method {
      background: #fca5a5;
      color: #7f1d1d;
    }

    .swagger-ui .opblock.opblock-patch {
      border-color: #e9d5ff;
      background: #faf5ff;
    }

    .swagger-ui .opblock.opblock-patch .opblock-summary-method {
      background: #d8b4fe;
      color: #581c87;
    }

    /* ── Operation Summary ── */
    .swagger-ui .opblock-summary {
      padding: 16px 20px;
      cursor: pointer;
      transition: background 0.2s ease;
    }

    .swagger-ui .opblock-summary:hover {
      background: rgba(255, 255, 255, 0.5);
    }

    .swagger-ui .opblock-summary-method {
      font-size: 13px;
      font-weight: 700;
      min-width: 80px;
      padding: 8px 16px;
      text-align: center;
      border-radius: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-family: 'Fira Code', monospace;
    }

    .swagger-ui .opblock-summary-path {
      font-size: 15px;
      font-weight: 600;
      color: #374151;
      font-family: 'Fira Code', monospace;
      flex-grow: 1;
      padding: 0 16px;
    }

    .swagger-ui .opblock-summary-description {
      color: #6b7280;
      font-size: 14px;
    }

    /* ── Parameters & Responses ── */
    .swagger-ui .opblock-body {
      padding: 24px;
      background: white;
    }

    .swagger-ui .parameters-col_description {
      color: #6b7280;
      font-size: 14px;
    }

    .swagger-ui .parameter__name {
      font-weight: 600;
      color: #374151;
      font-family: 'Fira Code', monospace;
    }

    .swagger-ui .parameter__type {
      color: #7c3aed;
      font-size: 12px;
      font-family: 'Fira Code', monospace;
    }

    /* ── Response Tabs ── */
    .swagger-ui .responses-inner {
      padding: 20px;
      background: #f9fafb;
      border-radius: 8px;
    }

    .swagger-ui .response-col_status {
      font-weight: 700;
      font-family: 'Fira Code', monospace;
    }

    .swagger-ui .response-col_status.response-200,
    .swagger-ui .response-col_status.response-201 {
      color: #059669;
    }

    .swagger-ui .response-col_status.response-400,
    .swagger-ui .response-col_status.response-404 {
      color: #dc2626;
    }

    /* ── Code Blocks ── */
    .swagger-ui .highlight-code {
      background: #1e293b;
      border-radius: 8px;
      padding: 16px;
    }

    .swagger-ui .highlight-code pre {
      color: #e2e8f0;
      font-family: 'Fira Code', monospace;
      font-size: 13px;
      line-height: 1.6;
    }

    /* ── Models Section ── */
    .swagger-ui .model-box {
      background: white;
      border-radius: 12px;
      padding: 20px;
      margin: 16px 0;
      border: 2px solid #e9d5ff;
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.06);
    }

    .swagger-ui .model-title {
      font-size: 18px;
      font-weight: 600;
      color: #7c3aed;
      margin-bottom: 12px;
    }

    .swagger-ui .model {
      font-family: 'Fira Code', monospace;
      font-size: 13px;
    }

    /* ── Buttons ── */
    .swagger-ui .btn {
      border-radius: 8px;
      font-weight: 600;
      padding: 10px 20px;
      font-size: 14px;
      transition: all 0.2s ease;
      border: none;
      cursor: pointer;
    }

    .swagger-ui .btn.execute {
      background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%);
      color: white;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
    }

    .swagger-ui .btn.execute:hover {
      box-shadow: 0 6px 16px rgba(124, 58, 237, 0.4);
      transform: translateY(-2px);
    }

    .swagger-ui .btn.cancel {
      background: #f3f4f6;
      color: #374151;
    }

    .swagger-ui .btn.cancel:hover {
      background: #e5e7eb;
    }

    /* ── Try it out ── */
    .swagger-ui .try-out__btn {
      background: #fef3c7;
      color: #92400e;
      border: 2px solid #fcd34d;
      font-weight: 600;
    }

    .swagger-ui .try-out__btn:hover {
      background: #fde68a;
    }

    /* ── Input Fields ── */
    .swagger-ui input[type=text],
    .swagger-ui input[type=password],
    .swagger-ui input[type=email],
    .swagger-ui textarea,
    .swagger-ui select {
      border: 2px solid #e9d5ff;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 14px;
      font-family: 'Fira Code', monospace;
      transition: border-color 0.2s ease;
    }

    .swagger-ui input[type=text]:focus,
    .swagger-ui input[type=password]:focus,
    .swagger-ui input[type=email]:focus,
    .swagger-ui textarea:focus,
    .swagger-ui select:focus {
      outline: none;
      border-color: #7c3aed;
      box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {
      width: 12px;
      height: 12px;
    }

    ::-webkit-scrollbar-track {
      background: #f3f4f6;
    }

    ::-webkit-scrollbar-thumb {
      background: #c4b5fd;
      border-radius: 6px;
    }

    ::-webkit-scrollbar-thumb:hover {
      background: #a78bfa;
    }

    /* ── Authorization ── */
    .swagger-ui .auth-wrapper {
      background: white;
      border-radius: 12px;
      /* padding: 24px;
      border: 2px solid #e9d5ff;
      box-shadow: 0 4px 12px rgba(139, 92, 246, 0.08); */
    }

    .swagger-ui .auth-btn-wrapper {
      padding: 16px 0;
    }

    .swagger-ui .authorize {
      background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%);
      color: white;
      border: none;
      padding: 10px 24px;
      border-radius: 8px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
    }

    .swagger-ui .authorize:hover {
      box-shadow: 0 6px 16px rgba(124, 58, 237, 0.4);
      transform: translateY(-2px);
    }

    /* ── Topbar (Hide default) ── */
    .swagger-ui .topbar {
      display: none;
    }

    /* ── Scheme Container ── */
    .swagger-ui .scheme-container {
      background: white;
      padding: 20px;
      border-radius: 12px;
      margin: 20px 0;
      border: 2px solid #e9d5ff;
      box-shadow: 0 2px 8px rgba(139, 92, 246, 0.06);
    }
  </style>
</head>

<body>
  <div class="custom-header">
    <h1>
      P.A DEV API Documentation
    </h1>
    <p>Internal API Documentation - Support Ticket System</p>
  </div>

  <div id="swagger-ui"></div>

  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" charset="UTF-8"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
  <script>
    window.onload = function() {
      const spec = \`${openapiSpec.replace(/`/g, "\\`").replace(/\$/g, "\\$")}\`;

      window.ui = SwaggerUIBundle({
        spec: jsyaml.load(spec),
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout",
        defaultModelsExpandDepth: 3,
        defaultModelExpandDepth: 3,
        docExpansion: "list",
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        syntaxHighlight: {
          activate: true,
          theme: "monokai"
        },
        tryItOutEnabled: true,
        requestSnippetsEnabled: true,
        persistAuthorization: true
      });
    };
  </script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js"></script>
</body>
</html>`;

// Ghi file
fs.writeFileSync(
  "public/api-docs.html",
  html,
  "utf8"
);
console.log("✅ Swagger UI documentation built successfully: api-docs.html");
