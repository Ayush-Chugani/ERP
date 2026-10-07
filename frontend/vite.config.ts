import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
export default defineConfig({
 plugins: [react(), VitePWA({
  registerType: 'prompt', injectRegister: false,
  manifest: {
   name: 'SIMS Reference Workspace', short_name: 'SIMS',
   description: 'Student information reference workspace',
   start_url: '/', scope: '/', display: 'standalone',
   theme_color: '#174d43', background_color: '#f4f6f5',
   icons: [{src:'/icon-192.png',sizes:'192x192',type:'image/png'},
    {src:'/icon-512.png',sizes:'512x512',type:'image/png'},
    {src:'/icon-maskable.png',sizes:'512x512',type:'image/png',purpose:'maskable'}]
  },
  workbox: {
   globPatterns: ['**/*.{js,css,html,png,webmanifest}'],
   navigateFallback: '/index.html',
   navigateFallbackDenylist: [/^\/api(?:\/|$)/, /^\/admin(?:\/|$)/],
   skipWaiting: false, clientsClaim: true,
   runtimeCaching: [{urlPattern: /\/api(?:\/|$)|\/admin(?:\/|$)/,handler:'NetworkOnly'}]
  },
  devOptions: {enabled:false}
 })],
 server:{port:5173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000'}},
 preview:{host:'127.0.0.1',port:4173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000'}}
});
