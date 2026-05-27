import { schema, truthy, pattern } from "@stoplight/spectral-functions";
import privateEndpoint from "./functions/private-must-have-401-403.js";
import enumHasDescription from "./functions/enum-has-description.js";
import hasRequestBodyMustHave400 from "./functions/has-request-body-must-have-400.js";
import {
  clientIdMustNotBeReadonly,
  serverIdMustBeReadonly,
} from "./functions/id-readonly-check.js";

export default {
  rules: {
    /**
     * Mọi ID field trong response phải có readOnly: true
     * Severity: error — vi phạm cứng, block CI
     */
    "response-id-must-be-readonly": {
      message: "{{error}}",
      severity: "error",
      given: "$.paths[*][*].responses[*].content",
      then: { function: serverIdMustBeReadonly },
    },

    /**
     * ID field trong requestBody không được có readOnly: true
     * Severity: warn — nhắc nhở
     */
    "request-id-must-not-be-readonly": {
      message: "{{error}}",
      severity: "warn",
      given: "$.paths[*][*].requestBody.content",
      then: { function: clientIdMustNotBeReadonly },
    },

    "operation-id-verb-noun": {
      message:
        'operationId "{{value}}" sai format, operationId phải dùng camelCase và bắt đầu bằng động từ — ví dụ: listUsers, createOrder, reopenTicket.',
      severity: "error",
      given: "$.paths[*][get,post,put,patch,delete].operationId",
      then: {
        function: pattern,
        functionOptions: { match: "^[a-z][a-zA-Z0-9]+$" },
      },
    },

    "operation-must-have-summary": {
      message: 'Operation "{{property}}" phải có summary.',
      severity: "error",
      given: "$.paths[*][get,post,put,patch,delete]",
      then: { field: "summary", function: truthy },
    },

    "operation-must-have-description": {
      message: "Operation phải có description.",
      severity: "warn",
      given: "$.paths[*][get,post,put,patch,delete]",
      then: { field: "description", function: truthy },
    },

    "path-params-must-be-required": {
      message: 'Path parameter "{{property}}" phải có required: true.',
      severity: "error",
      given:
        '$.paths[*][get,post,put,patch,delete].parameters[?(@.in == "path")]',
      then: { field: "required", function: truthy },
    },

    "path-kebab-case": {
      message: "Path phải dùng kebab-case.",
      severity: "warn",
      given: "$.paths.*~",
      then: {
        function: pattern,
        functionOptions: { match: "^(/[a-z0-9-]+|/{[a-zA-Z0-9_]+})+$" },
      },
    },

    "schema-server-fields-must-be-readonly": {
      message: 'Trường "{{property}}" phải có readOnly: true',
      severity: "error",
      given: [
        "$.components.schemas[*].properties.created_at",
        "$.components.schemas[*].properties.updated_at",
      ],
      then: { field: "readOnly", function: truthy },
    },

    "schema-properties-must-have-description": {
      message: 'Property "{{property}}" phải có description.',
      severity: "info",
      given: "$.components.schemas[*].properties[*]",
      then: { field: "description", function: truthy },
    },

    "enum-schema-must-have-description": {
      message: "Schema có enum phải có description giải thích ý nghĩa.",
      severity: "warn",
      given: "$.components.schemas[*].properties[*]",
      then: { function: enumHasDescription },
    },

    "private-endpoint-must-have-401-403": {
      message: "{{error}}",
      severity: "error",
      given: "$.paths[*][get,post,put,patch,delete]",
      then: { function: privateEndpoint },
    },

    "operation-must-have-500": {
      message: "Operation thiếu response 500 (Internal Server Error).",
      severity: "warn",
      given: "$.paths[*][get,post,put,patch,delete]",
      then: { field: "responses.500", function: truthy },
    },

    "operation-with-id-must-have-404": {
      message: "Operation với path parameter phải có response 404 (Not Found).",
      severity: "warn",
      given: "$.paths[?(@property.match('.*{.*}.*'))][get,put,patch,delete]",
      then: { field: "responses.404", function: truthy },
    },

    "response-200-must-have-content": {
      message: "Response 200 phải có content/schema.",
      severity: "info",
      given: "$.paths[*][get,put,patch].responses.200",
      then: { field: "content", function: truthy },
    },

    "post-create-should-have-201": {
      message: "POST nên trả response 201 Created.",
      severity: "info",
      given: "$.paths[*].post.responses",
      then: { field: "201", function: truthy },
    },

    // New rule

    "must-have-servers": {
      message: "API phải khai báo ít nhất 1 server.",
      severity: "warn",
      given: "$",
      then: { field: "servers", function: truthy },
    },

    "info-must-have-contact": {
      message: "API phải có thông tin contact.",
      severity: "info",
      given: "$.info",
      then: { field: "contact", function: truthy },
    },

    "request-body-must-have-400": {
      severity: "warn",
      given: "$.paths[*][post,put,patch]",
      then: { function: hasRequestBodyMustHave400 },
    },

    "delete-must-have-204": {
      message: "DELETE nên trả 204 No Content.",
      severity: "warn",
      given: "$.paths[*].delete",
      then: { field: "responses.204", function: truthy },
    },

    "operation-must-have-tags": {
      message: "Operation phải có ít nhất 1 tag.",
      severity: "warn",
      given: "$.paths[*][get,post,put,patch,delete]",
      then: {
        field: "tags",
        function: schema,
        functionOptions: {
          schema: { type: "array", minItems: 1 },
        },
      },
    },
  },
};
