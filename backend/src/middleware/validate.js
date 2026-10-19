import { HttpError } from '../utils/httpError.js';

// validate(schema, 'body' | 'query' | 'params') -> replaces req[source] with the parsed value
export const validate = (schema, source = 'body') => (req, _res, next) => {
  const result = schema.safeParse(req[source]);
  if (!result.success) return next(new HttpError(400, 'Validation failed', result.error.flatten()));
  req[source] = result.data;
  next();
};
