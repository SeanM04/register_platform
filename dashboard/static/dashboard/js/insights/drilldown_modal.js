import {
    closeDrillDownModal,
    isDrillDownModalOpen,
    showDrillDownErrorModal,
    showDrillDownModal,
    showLoadingDrillDownModal,
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

export const isInsightsDrillDownModalOpen = isDrillDownModalOpen;
export const closeInsightsDrillDownModal = closeDrillDownModal;
export const showInsightsDrillDownLoadingModal = showLoadingDrillDownModal;
export const showInsightsDrillDownErrorModal = showDrillDownErrorModal;

export const showInsightsDrillDownModal = (payload, { onPageChange = null, onNavigate = null } = {}) => (
    showDrillDownModal(payload || {}, [], {
        onPageChange,
        onNavigate: typeof onNavigate === "function"
            ? (target) => {
                const items = Array.isArray(payload?.data) ? payload.data : [];
                const item = items.find((entry) => (
                    String(entry?.key || entry?.label || "") === String(target?.value || target?.bucket || "")
                ));
                onNavigate(item || target, payload?.type);
            }
            : null,
    })
);
