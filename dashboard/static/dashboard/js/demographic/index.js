import { createDemographicContext } from "./context.js";
import { initialiseFullscreenControls } from "./fullscreen.js";
import { initialiseGenderSection } from "./gender.js";
import { initialiseLocationSection } from "./locations.js";
import { initialiseLocationMixSection } from "./location_mix.js";
import { initialiseOriginMapSection } from "./origin_map.js";
import { initialiseProgrammeMixSection } from "./programme_mix.js";
import { renderStoryBanner } from "./narratives.js";

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

export const initialiseDemographicPage = () => {
    const context = createDemographicContext();
    const { data, elements } = context;

    renderStoryBanner(elements.storyBanner, data.genderRows, data.locationRows, data.programmeRows);

    const controllers = [
        initialiseGenderSection(context),
        initialiseLocationSection(context),
        initialiseLocationMixSection(context),
        initialiseProgrammeMixSection(context),
        initialiseOriginMapSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(elements.fullscreenButtons, resizeCharts);
};
