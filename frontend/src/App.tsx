import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { LandingPage } from './pages/LandingPage'
import { ConsolePage } from './pages/ConsolePage'
import { LivePage } from './pages/LivePage'

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/console" element={<ConsolePage />} />
      <Route path="/live" element={<LivePage />} />
    </Routes>
  )
}
