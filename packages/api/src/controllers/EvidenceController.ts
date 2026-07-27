import { Request, Response } from 'express';
import { EvidenceSchema } from '../models/EvidenceModel';

export class EvidenceController {
  public handleEvidence = async (req: Request, res: Response) => {
    try {
      const evidence = await EvidenceSchema.parseAsync(req.body);
      // Store evidence in SQLite database
      res.status(201).json(evidence);
    } catch (error) {
      res.status(400).json({ error: 'Invalid evidence payload' });
    }
  };
}
