const express = require('express');
const cookieParser = require('cookie-parser');
const healthRouter = require('./routes/health');
const errorHandler = require('./middleware/errors');

const app = express();

app.use(express.json());
app.use(cookieParser());

app.use('/api/health', healthRouter);

app.use(errorHandler);

module.exports = app;
