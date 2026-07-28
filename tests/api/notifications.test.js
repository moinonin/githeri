const request = require('supertest');
const express = require('express');
const notificationsRouter = require('../../src/routes/api/notifications');

const app = express();
app.use('/api', notificationsRouter);

describe('POST /api/notifications', () => {
  it('should return 202 with notification ID', async () => {
    const res = await request(app).post('/api/notifications').send({
      recipient: 'test@example.com',
      subject: 'Test Subject',
      body: 'Test Body',
      priority: 'high'
    });
    expect(res.status).toBe(202);
    expect(res.body).toHaveProperty('id');
  });

  it('should return 400 if required fields are missing', async () => {
    const res = await request(app).post('/api/notifications').send({
      recipient: 'test@example.com',
      subject: 'Test Subject'
      // missing body
    });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error');
  });
});