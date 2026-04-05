import { createAcademicLevelContext } from "./context.js";
import { initialiseFullscreenControls } from "./fullscreen.js";
import { initialiseGenderSection } from "./gender.js";
import { renderStoryBanner } from "./narratives.js";
import { initialisePassTrendSection } from "./pass_trend.js";
import { initialiseAcademicLevelSearch } from "./search.js";
import { initialiseTopProgrammeSection } from "./top_programme.js";

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

export const initialiseAcademicLevelPage = () => {
    const context = createAcademicLevelContext();
    const { elements, data } = context;

    initialiseAcademicLevelSearch(elements);
    renderStoryBanner(elements.storyBanner, data.levelRows, data.genderRows, data.programmeRows);

    const controllers = [
        initialiseGenderSection(context),
        initialisePassTrendSection(context),
        initialiseTopProgrammeSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(elements.fullscreenButtons, resizeCharts);
};
