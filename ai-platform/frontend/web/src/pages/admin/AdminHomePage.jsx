import { useEffect } from 'react';
import { ROUTES } from '../../app/routeCatalog';

export default function AdminHomePage() {
  useEffect(() => {
    window.location.replace(ROUTES.admin.operations);
  }, []);

  return null;
}
