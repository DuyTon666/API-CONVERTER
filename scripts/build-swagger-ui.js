const fs = require("fs");

// Đọc OpenAPI bundled spec
const openapiSpec = fs.readFileSync("dist/openapi-bundled.yaml", "utf8");
const escapedSpec = openapiSpec.replace(/`/g, "\\`").replace(/\$/g, "\\$");

const html = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>P.A DEV API Documentation</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.11.0/favicon-32x32.png" sizes="32x32" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.11.0/favicon-16x16.png" sizes="16x16" />
  <style>
    html {
      box-sizing: border-box;
      overflow: -moz-scrollbars-vertical;
      overflow-y: scroll;
    }
    *, *:before, *:after {
      box-sizing: inherit;
    }
    body {
      margin: 0;
      background: #fafafa;
    }
  </style>
</head>

<body>
  <div id="swagger-ui"></div>

  <script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" charset="UTF-8"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js"></script>

  <script>
    // Plugin thay thuật toán filter mặc định bằng Fuse.js fuzzy search.
    // Cùng approach với frontend/app/swagger/SwaggerView.tsx.
    var fuseFilterPlugin = function() {
      var fuseOptions = {
        keys: [
          { name: 'operationId', weight: 0.3 },
          { name: 'summary',     weight: 0.25 },
          { name: 'path',        weight: 0.2 },
          { name: 'method',      weight: 0.05 },
          { name: 'tag',         weight: 0.1 },
          { name: 'description', weight: 0.1 }
        ],
        threshold: 0.4,
        ignoreLocation: true,
        useExtendedSearch: true
      };

      return {
        fn: {
          opsFilter: function(taggedOps, phrase) {
            return taggedOps
              .map(function(tagObj, tag) {
                var ops = tagObj.get('operations');
                var entries = ops.toArray().map(function(op) {
                  return {
                    tag: tag,
                    path: op.get('path') || '',
                    method: op.get('method') || '',
                    operationId: op.getIn(['operation', 'operationId']) || '',
                    summary: op.getIn(['operation', 'summary']) || '',
                    description: op.getIn(['operation', 'description']) || ''
                  };
                });
                var fuse = new Fuse(entries, fuseOptions);
                var matched = new Set(fuse.search(phrase).map(function(r) { return r.refIndex; }));
                return tagObj.set(
                  'operations',
                  ops.filter(function(op, i) { return matched.has(i); })
                );
              })
              .filter(function(tagObj) {
                return tagObj.get('operations').size > 0;
              });
          }
        }
      };
    };

    window.onload = function() {
      var parsedSpec = jsyaml.load(\`${escapedSpec}\`);

      window.ui = SwaggerUIBundle({
        spec: parsedSpec,
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl,
          fuseFilterPlugin
        ],
        layout: "StandaloneLayout",
        filter: true
      });
    };
  </script>
</body>
</html>`;

fs.writeFileSync("public/api-docs.html", html, "utf8");
console.log("✅ Swagger UI documentation built successfully: api-docs.html");
