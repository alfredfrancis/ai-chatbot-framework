import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';


import {LayoutComponent} from './dashboard/layout/layout.component'
const routes: Routes = [
  { path: '', redirectTo: 'agent/default', pathMatch: 'full' },
	{
		path: 'agent/default',
    component: LayoutComponent,
    loadChildren: './agent/agent.module#AgentModule' 
	},
	{
		path: '**',
		redirectTo: 'agent/default'
	}
];

@NgModule({
  imports: [RouterModule.forRoot(routes, {useHash: true})],
  exports: [RouterModule]
})
export class AppRoutingModule { }
