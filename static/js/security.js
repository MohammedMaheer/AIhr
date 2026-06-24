(function () {
    "use strict";

    function getCookie(name) {
        return document.cookie
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith(name + "="))
            ?.slice(name.length + 1) || "";
    }

    function isUnsafeMethod(method) {
        return !["GET", "HEAD", "OPTIONS"].includes(String(method || "GET").toUpperCase());
    }

    function sameOrigin(input) {
        try {
            const rawUrl = input instanceof Request ? input.url : String(input);
            const url = new URL(rawUrl, window.location.href);
            return url.origin === window.location.origin;
        } catch (_) {
            return true;
        }
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = function securedFetch(input, init) {
        const options = init ? { ...init } : {};
        const method = options.method || (input instanceof Request ? input.method : "GET");

        if (sameOrigin(input) && isUnsafeMethod(method)) {
            const token = decodeURIComponent(getCookie("csrf_token"));
            if (token) {
                const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
                if (!headers.has("X-CSRF-Token")) {
                    headers.set("X-CSRF-Token", token);
                }
                options.headers = headers;
                options.credentials = options.credentials || "same-origin";
            }
        }

        return originalFetch(input, options);
    };

    window.escapeHtml = window.escapeHtml || function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    };

    window.escapeAttr = window.escapeAttr || function escapeAttr(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/`/g, "&#96;");
    };

    window.safeNumber = window.safeNumber || function safeNumber(value, fallback = 0, min = 0, max = 100) {
        const number = Number(value);
        if (!Number.isFinite(number)) return fallback;
        return Math.min(max, Math.max(min, number));
    };

    window.sanitizeGeneratedHtml = window.sanitizeGeneratedHtml || function sanitizeGeneratedHtml(html) {
        const template = document.createElement("template");
        template.innerHTML = html || "";

        template.content
            .querySelectorAll("script, iframe, object, embed, link, meta, base, form, input, button")
            .forEach((node) => node.remove());

        template.content.querySelectorAll("*").forEach((node) => {
            Array.from(node.attributes).forEach((attr) => {
                const name = attr.name.toLowerCase();
                const value = (attr.value || "").trim().toLowerCase();
                if (name.startsWith("on") || name === "srcdoc" || name === "style") {
                    node.removeAttribute(attr.name);
                }
                if ((name === "href" || name === "src" || name === "xlink:href") && value.startsWith("javascript:")) {
                    node.removeAttribute(attr.name);
                }
            });
        });

        return template.innerHTML;
    };
})();
