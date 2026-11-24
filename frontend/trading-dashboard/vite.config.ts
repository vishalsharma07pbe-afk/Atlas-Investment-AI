import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins:[react()],
  build:{
    rollupOptions:{
      output:{
        manualChunks:{
          "react-vendor":["react","react-dom"],
          "chart-vendor":["lightweight-charts"]
        }
      }
    }
  },
  server:{
    host:"0.0.0.0",
    port:5173,
    proxy:{
      "/api":{target:"http://backend:8080",changeOrigin:false},
      "/intelligence":{target:"http://intelligence:8000",changeOrigin:true,rewrite:path=>path.replace(/^\/intelligence/,"")}
    }
  }
});
