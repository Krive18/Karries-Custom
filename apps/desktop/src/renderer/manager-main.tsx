import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ManagerApp } from "./ManagerApp";
import { initializeFontScale } from "./fontScale";
import { initializeTheme } from "./theme";
import "./styles.css";
import "./styles/karries-design-system.css";
import "./styles/karries-product-pages.css";


initializeTheme();
initializeFontScale();

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <ManagerApp />
  </StrictMode>
);
