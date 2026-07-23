import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { DeveloperApp } from "./DeveloperApp";
import "./styles.css";


createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <DeveloperApp />
  </StrictMode>
);
