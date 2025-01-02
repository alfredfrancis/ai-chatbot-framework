"use client";

import React from "react";
import Image, { StaticImageData } from "next/image";
import book1 from "@/public/sidebar/book-1.svg";
import coffee1 from "@/public/sidebar/coffee-1.svg";
import logo from "@/public/sidebar/logo.png";
import home1 from "@/public/sidebar/home-1.svg";
import messageSquare1 from "@/public/sidebar/message-square-1.svg";
import settings1 from "@/public/sidebar/home-1.svg";
import database1 from "@/public/sidebar/home-1.svg";
import code1 from "@/public/sidebar/home-1.svg";
import "./Sidebar.css";
import Link from 'next/link';

const Sidebar = () => {
  const menuItems = [
    { label: "Intents", icon: coffee1, path: "/admin/intents" },
    { label: "Entities", icon: book1, path: "/admin/entities" },
    { label: "Chat", icon: messageSquare1, path: "/admin/chat" },
  ];

  const settingsItems = [
    { label: "ML Settings", icon: settings1, path: "/admin/settings/ml" },
    { label: "Data Management", icon: database1, path: "/admin/settings/data" },
    { label: "Integrations", icon: code1, path: "/admin/settings/integrations" },
  ];

  return (
    <aside className="fixed top-0 left-0 h-screen w-72 bg-white shadow-lg flex flex-col p-5 overflow-y-auto">
      <div className="sidebar-header">
        <div className="logo-container">
          <Image className="logo" src={logo as StaticImageData} alt="logo" />
          <h1 className="text-green-500 font-medium text-lg">Admin Panel</h1>
        </div>
      </div>
      <hr className="divider"/>
      <nav className="menu">
        {menuItems.map((item, index) => (
          <Link href={item.path} key={index}>
            <div className="menu-item flex items-center gap-3 p-3 rounded-lg bg-white transition-colors duration-300 cursor-pointer hover:bg-green-100">
              <div className="menu-icon w-9 h-9 p-2.5 bg-green-100 rounded-lg flex items-center justify-center">
                <Image src={item.icon as StaticImageData} alt={item.label} />
              </div>
              <span className="menu-label text-gray-600 text-sm">{item.label}</span>
            </div>
          </Link>
        ))}
      </nav>
      <div className="sidebar-section mt-5">
        <h2 className="section-title text-green-500 text-sm font-medium tracking-wider mb-2.5">Settings</h2>
        <nav className="menu">
          {settingsItems.map((item, index) => (
            <Link href={item.path} key={index}>
              <div className="menu-item flex items-center gap-3 p-3 rounded-lg bg-white transition-colors duration-300 cursor-pointer hover:bg-green-100">
                <div className="menu-icon w-9 h-9 p-2.5 bg-green-100 rounded-lg flex items-center justify-center">
                  <Image src={item.icon as StaticImageData} alt={item.label} />
                </div>
                <span className="menu-label text-gray-600 text-sm">{item.label}</span>
              </div>
            </Link>
          ))}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;