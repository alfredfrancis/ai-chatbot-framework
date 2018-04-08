import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LayoutComponent } from './layout/layout.component';
import { SidebarComponent } from './sidebar/sidebar.component';

import {RouterModule } from '@angular/router';


/* Material UI imports begins here */
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';

import { MatToolbarModule, MatIconModule,
   MatListModule,MatSidenavModule, MatFormFieldModule
   
} from '@angular/material';


/* Material UI imports ends here */

@NgModule({
  imports: [
    CommonModule,
    RouterModule,
    MatToolbarModule,
    MatIconModule, 
    MatListModule,
    MatSidenavModule,
    MatFormFieldModule
  ],
  declarations: [LayoutComponent, SidebarComponent]
})
export class DashboardModule { }
