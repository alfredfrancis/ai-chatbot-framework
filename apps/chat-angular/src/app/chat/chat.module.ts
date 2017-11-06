import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatComponent } from './chat.component';
import { ChatService } from './chat.service';
import { RouterModule } from '@angular/router';
import { ChatRoutes } from './chat.routing';
import {MatButtonModule, MatCheckboxModule} from '@angular/material';

@NgModule({
  imports: [
    CommonModule,
    RouterModule.forRoot(ChatRoutes),
    MatButtonModule, MatCheckboxModule
  ],
  declarations: [ChatComponent],
  exports: [ChatComponent],
  entryComponents: [ChatComponent],
  providers: [
    ChatService
  ],
})
export class ChatModule { }
