const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({testDir:'./tests/browser',use:{baseURL:process.env.BASE_URL||'http://localhost:8080',viewport:{width:390,height:844},trace:'retain-on-failure'},projects:[{name:'mobile-390'},{name:'mobile-360',use:{viewport:{width:360,height:800}}}]});
