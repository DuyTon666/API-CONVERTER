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

    // Plugin chèn x-error-responses vào bảng Responses. Cùng approach với
    // frontend/app/swagger/SwaggerView.tsx (bọc component "response" số ít,
    // dùng system.React.createElement thay vì JSX vì trang này không có
    // React của Next mà chỉ có React đóng gói sẵn trong swagger-ui-bundle.js).
    var errorCodesStyleInjected = false;
    var errorCodesCategoryChipClass = {
      Auth: 'auth',
      Input: 'input',
      Business: 'business',
      State: 'state',
      Validation: 'validation',
      'Not Found': 'notfound'
    };

    function errorCodesEscapeHtml(value) {
      return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function errorCodesCategoryClass(category) {
      return errorCodesCategoryChipClass[category] || 'default';
    }

    function ensureErrorCodesStyleInjected() {
      if (errorCodesStyleInjected) return;
      errorCodesStyleInjected = true;
      var style = document.createElement('style');
      style.textContent =
        '.errcodes-details-cell { padding: 0 20px 12px !important; border-bottom: none !important; }' +
        '.errcodes-details { margin-top: 10px; }' +
        '.errcodes-details summary { cursor: pointer; font-size: 13px; font-weight: 600; color: #3b4151; list-style: none; }' +
        '.errcodes-details summary::-webkit-details-marker { display: none; }' +
        '.errcodes-details summary::before { content: "▸"; display: inline-block; width: 12px; transition: transform 0.15s ease; }' +
        '.errcodes-details[open] summary::before { transform: rotate(90deg); }' +
        '.errcodes-table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12.5px; }' +
        '.errcodes-table th, .errcodes-table td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #e8e8e8; }' +
        '.errcodes-table th { color: #6b7280; font-weight: 600; }' +
        '.errcodes-chip { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600; white-space: nowrap; }' +
        '.errcodes-chip.auth { background: #dbeafe; color: #1e40af; }' +
        '.errcodes-chip.input { background: #ede9fe; color: #5b21b6; }' +
        '.errcodes-chip.business { background: #dcfce7; color: #166534; }' +
        '.errcodes-chip.state { background: #ffedd5; color: #9a3412; }' +
        '.errcodes-chip.validation { background: #fce7f3; color: #9d174d; }' +
        '.errcodes-chip.notfound { background: #e0f2fe; color: #075985; }' +
        '.errcodes-chip.default { background: #f3f4f6; color: #4b5563; }';
      document.head.appendChild(style);
    }

    function buildErrorTableHtml(entries, defaultOpen) {
      var rows = entries.map(function(e) {
        return '' +
          '<tr>' +
          '<td>' + errorCodesEscapeHtml(e.code) + '</td>' +
          '<td><span class="errcodes-chip ' + errorCodesCategoryClass(e.category) + '">' + errorCodesEscapeHtml(e.category) + '</span></td>' +
          '<td>' + errorCodesEscapeHtml(e.message) + '</td>' +
          '</tr>';
      }).join('');
      return '' +
        '<details class="errcodes-details"' + (defaultOpen ? ' open' : '') + '>' +
        '<summary>' + entries.length + ' mã lỗi</summary>' +
        '<table class="errcodes-table">' +
        '<thead><tr><th>Mã</th><th>Nhóm</th><th>Ý nghĩa</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
        '</table>' +
        '</details>';
    }

    var errorCodesPlugin = function() {
      return {
        wrapComponents: {
          response: function(Original, system) {
            return function(props) {
              ensureErrorCodesStyleInjected();

              var operation = system.specSelectors.specJson().getIn(['paths', props.path, props.method]);
              var errorMapForOperation = operation && operation.getIn(['x-error-responses']);
              var entryForStatus = errorMapForOperation && errorMapForOperation.get(String(props.code));
              var entriesForThisStatus = entryForStatus && entryForStatus.toJS ? entryForStatus.toJS() : entryForStatus;

              if (!entriesForThisStatus || entriesForThisStatus.length === 0) {
                return system.React.createElement(Original, props);
              }

              var defaultOpen = errorMapForOperation.keySeq().size === 1;

              return system.React.createElement(
                system.React.Fragment,
                null,
                system.React.createElement(Original, props),
                system.React.createElement(
                  'tr',
                  null,
                  system.React.createElement('td', {
                    colSpan: 100,
                    className: 'errcodes-details-cell',
                    dangerouslySetInnerHTML: {
                      __html: buildErrorTableHtml(entriesForThisStatus, defaultOpen)
                    }
                  })
                )
              );
            };
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
          fuseFilterPlugin,
          errorCodesPlugin
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
