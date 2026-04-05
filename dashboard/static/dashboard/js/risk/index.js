import { createRiskContext } from "./context.js?v=20260403-risk-storyflow10";
import { initialiseDistributionSection } from "./distribution.js?v=20260403-risk-storyflow10";
import { initialiseDriversSection } from "./drivers.js?v=20260403-risk-storyflow10";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260403-risk-storyflow10";
import { initialiseLevelsSection } from "./levels.js?v=20260403-risk-storyflow10";
import { renderStoryBanner } from "./narratives.js?v=20260403-risk-storyflow10";
import { initialiseProgrammesSection } from "./programmes.js?v=20260403-risk-storyflow10";
import { initialiseRiskSearch } from "./search.js?v=20260403-risk-storyflow10";

const initialiseChartResizeHandling = (controllers, resizeCharts) => {
    const charts = controllers
        .map((controller) => controller.getChart())
        .filter(Boolean);

    if (!charts.length) {
        return;
    }

    window.addEventListener("resize", resizeCharts);

    if (!window.ResizeObserver) {
        return;
    }

    const observer = new ResizeObserver(() => {
        resizeCharts();
    });

    charts.forEach((chart) => {
        observer.observe(chart.getDom());
    });
};

export const initialiseRiskPage = () => {
    const context = createRiskContext();
    const { data, elements } = context;

    renderStoryBanner(
        elements.storyBanner,
        data.distributionRows,
        data.driverRows,
        data.levelRows,
        data.programmeRows,
    );

    const controllers = [
        initialiseDistributionSection(context),
        initialiseDriversSection(context),
        initialiseLevelsSection(context),
        initialiseProgrammesSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseRiskSearch(elements.searchForm, elements.searchInput);
    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(elements.fullscreenButtons, resizeCharts);
};
