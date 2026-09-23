import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Book from './pages/Book'
import BookingSuccess from './pages/BookingSuccess'
import Home from './pages/Home'
import MyAppointments from './pages/MyAppointments'

const Admin = lazy(() => import('./pages/Admin')) // owner-only, keep it out of the public bundle

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/book" element={<Book />} />
        <Route path="/booking/success" element={<BookingSuccess />} />
        <Route path="/my-appointments" element={<MyAppointments />} />
        <Route
          path="/admin"
          element={
            <Suspense fallback={null}>
              <Admin />
            </Suspense>
          }
        />
        <Route path="*" element={<div className="panel narrow"><h1>Page not found</h1></div>} />
      </Route>
    </Routes>
  )
}
