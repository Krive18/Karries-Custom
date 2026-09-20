import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { initializeFontScale } from "./fontScale";
import { initializeTheme } from "./theme";
import "./styles.css";
import "./styles/karries-design-system.css";
import "./styles/karries-product-pages.css";


initializeTheme();
initializeFontScale();

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
