import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DeveloperApp } from "./DeveloperApp";
import "./styles.css";
import "./styles/developer-silver-lab.css";


document.documentElement.dataset.themePreference = "light";
document.documentElement.dataset.theme = "light";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <DeveloperApp />
  </StrictMode>
);
