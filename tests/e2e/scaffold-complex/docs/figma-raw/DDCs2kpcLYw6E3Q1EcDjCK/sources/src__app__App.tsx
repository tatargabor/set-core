import { RouterProvider } from 'react-router';
import { router } from './routes';
import { Toaster } from 'sonner';

function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="top-right" />
    </>
  );
}

export default App;
