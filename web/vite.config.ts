import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Hosted at https://ibiraheel.com/demos/lens-tolerance-yield/
export default defineConfig({ base: "/demos/lens-tolerance-yield/", plugins: [react()] });
