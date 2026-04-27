// Local ESLint config — extends Codacy rules and adds browser globals
// so that document, window, fetch, etc. are not flagged as undefined
// in front-end scripts loaded via <script> tags.
import codacy from "./.codacy/tools-configs/eslint.config.mjs";

const browserGlobals = {
    window: "readonly",
    document: "readonly",
    navigator: "readonly",
    sessionStorage: "readonly",
    localStorage: "readonly",
    fetch: "readonly",
    requestAnimationFrame: "readonly",
    cancelAnimationFrame: "readonly",
    setTimeout: "readonly",
    clearTimeout: "readonly",
    setInterval: "readonly",
    clearInterval: "readonly",
    console: "readonly",
    URLSearchParams: "readonly",
    FormData: "readonly",
    Event: "readonly",
    CustomEvent: "readonly",
    MutationObserver: "readonly",
    IntersectionObserver: "readonly",
    ResizeObserver: "readonly",
    AbortController: "readonly",
};

export default [
    ...codacy,
    {
        files: ["**/static/**/*.js"],
        languageOptions: {
            globals: browserGlobals,
        },
    },
];
