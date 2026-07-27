/* MediVision Mobile — runtime config.
   API_BASE: your hosted Flask backend (Phase 0). Can be overridden at runtime
   from the Login screen "Server" setting; the saved value wins. */
window.MV_CONFIG = {
  // STANDALONE: true = runs fully on the phone (no PC/server needed) using local.js.
  // Set false to use your hosted/PC backend (API_BASE) + owner dashboard (OWNER_BASE).
  STANDALONE: true,
  // CHANGE THIS to your deployed backend before building the APK.
  // For local testing against a PC on the same Wi-Fi use http://<PC-LAN-IP>:5001
  API_BASE: "http://192.168.0.101:5001",
  // Central owner registry (heartbeat + license). Set this to your VPS URL once it's
  // deployed (see owner/DEPLOY.md) and rebuild — the app will then require a live
  // check-in to run, on top of the local device code below.
  // Leave "" (current state) to run on the LOCAL device-code lock only.
  OWNER_BASE: "",
  APP_NAME: "MediVision",
  // Plan → feature map. Mirror server-side gating; client only hides/disables UI.
  PLANS: {
    inventory: { label: "Inventory",            price: 200,  features: ["stock","scan","alerts"] },
    billing:   { label: "Inventory + Billing",  price: 500,  features: ["stock","scan","alerts","bill","print","khata","basic_reorder"] },
    smart:     { label: "Smart Shop",           price: 700,  features: ["stock","scan","alerts","bill","print","khata","basic_reorder","ai_reorder","compare","profit","loyalty","twilio","swipe_order","cust_family"] },
    pro:       { label: "Wholesale / Pro",      price: 1000, features: ["stock","scan","alerts","bill","print","khata","basic_reorder","ai_reorder","compare","profit","loyalty","twilio","swipe_order","cust_family","wholesale_order","tally","multi_counter","delivery","face_attend","item_images","translator"] },
    max:       { label: "Max (Fleet)",          price: 1599, features: ["stock","scan","alerts","bill","print","khata","basic_reorder","ai_reorder","compare","profit","loyalty","twilio","swipe_order","cust_family","wholesale_order","tally","multi_counter","delivery","face_attend","item_images","translator","multi_branch","whatsapp_biz","n8n_autoorder","image_dataset","cloud_backup"] }
  }
};
