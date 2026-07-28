const express = require('express');
const app = express();
const notificationsRouter = require('./src/routes/api/notifications');

app.use('/api', notificationsRouter);

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});