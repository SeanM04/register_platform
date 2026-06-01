import {
    closeDrillDownModal,
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showDrillDownModal,
    showLoadingDrillDownModal,
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

export const isRiskDrillDownModalOpen = isDrillDownModalOpen;
export const closeRiskDrillDownModal = closeDrillDownModal;
export const showRiskDrillDownLoadingModal = showLoadingDrillDownModal;
export const showRiskDrillDownErrorModal = showDrillDownErrorModal;

export const showRiskDrillDownModal = (payload, options = {}) => (
    showDrillDownModal(payload || {}, [], options)
);
